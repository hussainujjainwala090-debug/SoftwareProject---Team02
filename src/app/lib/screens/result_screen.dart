import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../state/session.dart';
import '../widgets/common.dart';
import 'report_screen.dart';

/// UI-4: Diagnosis result (FR-04 to FR-09, FR-14, FR-16; SD-2). Agronomists
/// also get a "Confirm or correct" panel (UC-01 extension).
class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, required this.diagnosisId});
  final String diagnosisId;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  Diagnosis? _d;
  SpreadRiskInfo? _risk;
  String? _error;
  bool _showOverlay = true;
  bool? _feedback;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<ApiClient>();
    try {
      final d = await api.diagnosis(widget.diagnosisId);
      setState(() {
        _d = d;
        _feedback = d.feedbackCorrect;
        _error = null;
      });
      // SD-2 step 2: refresh the spread risk with the current (or cached) weather.
      if (!d.isUncertain && d.diseaseId != null) {
        final risk = await api.spreadRisk(widget.diagnosisId);
        if (mounted) setState(() => _risk = risk);
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  Future<void> _sendFeedback(bool correct) async {
    final ok = await runWithError(context, () async {
      await context.read<ApiClient>().feedback(widget.diagnosisId, correct);
      return true;
    });
    if (ok == true) setState(() => _feedback = correct);
  }

  Future<void> _export() async {
    final report = await runWithError(context, () => context.read<ApiClient>().createReport(widget.diagnosisId));
    if (report != null && mounted) {
      await Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => ReportScreen(diagnosisId: widget.diagnosisId, latest: report)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<Session>().user!;
    final d = _d;
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnosis')),
      body: d == null
          ? Center(child: _error == null ? const CircularProgressIndicator() : MessageBox(_error!))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                _image(d),
                const SizedBox(height: 8),
                if (d.overlayUrl != null)
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: false, label: Text('Original')),
                      ButtonSegment(value: true, label: Text('Overlay')),
                    ],
                    selected: {_showOverlay},
                    onSelectionChanged: (s) => setState(() => _showOverlay = s.first),
                  ),
                _diagnosisCard(d),
                if (d.isUncertain) _uncertainCard(d) else ...[
                  if (d.diseaseId != null) _severityCard(d),
                  if (d.diseaseId != null) _riskCard(d),
                  if (d.treatments.isNotEmpty) _TreatmentTabs(treatments: d.treatments),
                ],
                if (user.isAgronomist || user.isAdmin) _ReviewPanel(diagnosis: d, onDone: _load),
                if (!user.isAgronomist) _feedbackRow(),
                const SizedBox(height: 12),
                FilledButton.icon(
                  icon: const Icon(Icons.picture_as_pdf_outlined),
                  label: const Text('Save and export report'),
                  onPressed: _export,
                ),
              ]),
            ),
    );
  }

  Widget _image(Diagnosis d) {
    final url = _showOverlay && d.overlayUrl != null ? d.overlayUrl : d.imageUrl;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: AspectRatio(
        aspectRatio: 1,
        child: url == null
            ? const ColoredBox(color: Colors.black12)
            : Image.network(url, fit: BoxFit.cover,
                errorBuilder: (_, _, _) => const Center(child: Icon(Icons.broken_image_outlined, size: 48))),
      ),
    );
  }

  Widget _diagnosisCard(Diagnosis d) => InfoCard(
        title: d.label,
        trailing: d.reviewedBy != null ? const Chip(label: Text('Reviewed')) : null,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Confidence: ${(d.confidence * 100).round()}%'),
          const SizedBox(height: 6),
          LinearProgressIndicator(value: d.confidence, minHeight: 8),
          const SizedBox(height: 6),
          Text('${cropName(d.cropType)} · ${formatDate(d.capturedAt)}'),
        ]),
      );

  Widget _uncertainCard(Diagnosis d) => InfoCard(
        title: 'Uncertain result',
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(d.advice ?? 'Retake the photo or ask an agronomist.'),
          const SizedBox(height: 8),
          const Text('An agronomist can see this result in their review list.'),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Retake photo'),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ]),
      );

  Widget _severityCard(Diagnosis d) => InfoCard(
        title: 'Severity',
        trailing: LevelChip(d.severityLevel),
        child: Text('Affected leaf area: ${d.affectedAreaPct?.toStringAsFixed(1) ?? '-'}%'),
      );

  Widget _riskCard(Diagnosis d) {
    final level = _risk?.level ?? d.spreadRisk;
    final weather = _risk?.weather ?? d.weather;
    return InfoCard(
      title: 'Spread risk',
      trailing: LevelChip(level),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(_risk?.explanation ?? d.spreadRiskExplanation ?? 'Spread risk unavailable.'),
        const SizedBox(height: 4),
        Text('Weather: ${weather?.summary ?? 'unavailable'}'),
        if (weather?.notice != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(weather!.notice!, style: TextStyle(color: Colors.orange.shade800)),
          ),
      ]),
    );
  }

  Widget _feedbackRow() => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          const Expanded(child: Text('Was this correct?')),
          if (_feedback != null)
            Text(_feedback! ? 'You said yes. Thank you!' : 'You said no. Thank you!')
          else ...[
            OutlinedButton(style: compactButton, onPressed: () => _sendFeedback(true), child: const Text('Yes')),
            const SizedBox(width: 8),
            OutlinedButton(style: compactButton, onPressed: () => _sendFeedback(false), child: const Text('No')),
          ],
        ]),
      );
}

/// UI-4 items 7-8: organic, chemical and preventive treatments with safety warnings.
class _TreatmentTabs extends StatelessWidget {
  const _TreatmentTabs({required this.treatments});
  final List<Treatment> treatments;

  @override
  Widget build(BuildContext context) {
    const types = ['organic', 'chemical', 'preventive'];
    return DefaultTabController(
      length: types.length,
      child: Card(
        child: Column(children: [
          TabBar(tabs: [for (final t in types) Tab(text: titleCase(t))]),
          SizedBox(
            height: 170,
            child: TabBarView(children: [
              for (final type in types)
                ListView(padding: const EdgeInsets.all(12), children: [
                  for (final t in treatments.where((t) => t.type == type)) ...[
                    Text(t.guidance),
                    const SizedBox(height: 6),
                    Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Icon(Icons.warning_amber, size: 18, color: Colors.orange.shade800),
                      const SizedBox(width: 6),
                      Expanded(child: Text(t.safetyWarning, style: const TextStyle(fontStyle: FontStyle.italic))),
                    ]),
                  ],
                  if (!treatments.any((t) => t.type == type)) const Text('No advice of this type.'),
                ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

/// Agronomist review: confirm the diagnosis or correct it to another disease or "Healthy".
class _ReviewPanel extends StatefulWidget {
  const _ReviewPanel({required this.diagnosis, required this.onDone});
  final Diagnosis diagnosis;
  final Future<void> Function() onDone;

  @override
  State<_ReviewPanel> createState() => _ReviewPanelState();
}

class _ReviewPanelState extends State<_ReviewPanel> {
  static const healthy = '__healthy__';
  List<Disease>? _diseases;
  String? _choice;

  @override
  void initState() {
    super.initState();
    context.read<ApiClient>().diseases(crop: widget.diagnosis.cropType).then((list) {
      if (mounted) {
        setState(() {
          _diseases = list;
          _choice = widget.diagnosis.diseaseId ??
              (widget.diagnosis.isUncertain ? null : healthy);
        });
      }
    });
  }

  Future<void> _submit() async {
    final api = context.read<ApiClient>();
    final ok = await runWithError(context, () async {
      await api.review(widget.diagnosis.diagnosisId, _choice == healthy ? null : _choice);
      return true;
    });
    if (ok == true) {
      await widget.onDone();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Review saved')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final diseases = _diseases;
    return InfoCard(
      title: 'Agronomist review',
      child: diseases == null
          ? const LinearProgressIndicator()
          : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              DropdownButtonFormField<String>(
                key: const Key('reviewChoice'),
                initialValue: _choice,
                hint: const Text('Choose the correct result'),
                isExpanded: true,
                items: [
                  const DropdownMenuItem(value: healthy, child: Text('Healthy')),
                  for (final d in diseases) DropdownMenuItem(value: d.diseaseId, child: Text(d.name)),
                ],
                onChanged: (v) => setState(() => _choice = v),
              ),
              const SizedBox(height: 8),
              FilledButton(onPressed: _choice == null ? null : _submit, child: const Text('Confirm or correct')),
            ]),
    );
  }
}
