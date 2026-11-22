import 'dart:math';

import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../state/session.dart';
import '../widgets/common.dart';

/// UI-6: Farm owner dashboard (FR-11, FR-13): summary numbers, scans per week,
/// most common diseases and the current climate alert.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Future<Dashboard>? _data;
  String? _farmId;

  void _load(String farmId) {
    _farmId = farmId;
    _data = context.read<ApiClient>().dashboard(farmId);
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<Session>();
    final farm = session.selectedFarm;
    if (farm == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Dashboard')),
        body: const Padding(padding: EdgeInsets.all(16), child: MessageBox('Add a farm in Profile to see its dashboard.')),
      );
    }
    if (_farmId != farm.farmId) _load(farm.farmId);
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: RefreshIndicator(
        onRefresh: () async => setState(() => _load(farm.farmId)),
        child: ListView(padding: const EdgeInsets.all(16), children: [
          DropdownButtonFormField<String>(
            initialValue: farm.farmId,
            decoration: const InputDecoration(labelText: 'Farm', border: OutlineInputBorder()),
            items: [for (final f in session.farms) DropdownMenuItem(value: f.farmId, child: Text(f.name))],
            onChanged: (id) => session.selectFarm(id!),
          ),
          const SizedBox(height: 12),
          FutureBuilder<Dashboard>(
            future: _data,
            builder: (context, snap) {
              if (snap.hasError) return MessageBox('${snap.error}');
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final d = snap.data!;
              return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(children: [
                  _Stat('Scans', d.totalScans),
                  _Stat('Diseases', d.diseasesFound),
                  _Stat('Uncertain', d.uncertain),
                ]),
                InfoCard(
                  title: 'Scans per week',
                  child: _Bars(
                    labels: [for (final w in d.scansPerWeek) 'Wk ${w.week.split('-W').last}'],
                    values: [for (final w in d.scansPerWeek) w.scans],
                  ),
                ),
                InfoCard(
                  title: 'Most common diseases',
                  child: d.commonDiseases.isEmpty
                      ? const Text('No diseases found yet.')
                      : _HorizontalBars(d.commonDiseases),
                ),
                _ClimateAlert(d.climateAlert),
              ]);
            },
          ),
        ]),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) => Expanded(
        child: Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 14),
            child: Column(children: [
              Text(label),
              Text('$value', style: Theme.of(context).textTheme.headlineSmall),
            ]),
          ),
        ),
      );
}

/// Vertical bar chart (UI-6 item 4).
class _Bars extends StatelessWidget {
  const _Bars({required this.labels, required this.values});
  final List<String> labels;
  final List<int> values;

  @override
  Widget build(BuildContext context) {
    final maxV = max(1, values.fold<int>(0, max));
    return SizedBox(
      height: 150,
      child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        for (var i = 0; i < values.length; i++)
          Expanded(
            child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
              Text('${values[i]}'),
              Container(
                height: 100 * values[i] / maxV,
                margin: const EdgeInsets.symmetric(horizontal: 10),
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 4),
              Text(labels[i], style: Theme.of(context).textTheme.bodySmall),
            ]),
          ),
      ]),
    );
  }
}

/// Horizontal bars for the most common diseases (UI-6 item 5).
class _HorizontalBars extends StatelessWidget {
  const _HorizontalBars(this.counts);
  final Map<String, int> counts;

  @override
  Widget build(BuildContext context) {
    final maxV = counts.values.fold<int>(1, max);
    return Column(children: [
      for (final e in counts.entries)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(children: [
            SizedBox(width: 130, child: Text(e.key, overflow: TextOverflow.ellipsis)),
            Expanded(
              child: FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: e.value / maxV,
                child: Container(height: 16, color: Theme.of(context).colorScheme.tertiary),
              ),
            ),
            const SizedBox(width: 8),
            Text('${e.value}'),
          ]),
        ),
    ]);
  }
}

/// UI-6 item 6: current climate alert and spread-risk level.
class _ClimateAlert extends StatelessWidget {
  const _ClimateAlert(this.risk);
  final SpreadRiskInfo risk;

  @override
  Widget build(BuildContext context) {
    final color = levelColor(context, risk.level);
    return Card(
      shape: RoundedRectangleBorder(side: BorderSide(color: color, width: 2), borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(Icons.thunderstorm_outlined, color: color),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                  risk.level == null
                      ? 'Climate alert: spread risk unavailable'
                      : 'Climate alert: ${risk.level!.toUpperCase()} spread risk',
                  style: Theme.of(context).textTheme.titleMedium),
            ),
          ]),
          const SizedBox(height: 6),
          Text(risk.explanation),
          Text('Weather: ${risk.weather.summary}'),
          if (risk.weather.notice != null) Text(risk.weather.notice!, style: TextStyle(color: Colors.orange.shade800)),
        ]),
      ),
    );
  }
}
