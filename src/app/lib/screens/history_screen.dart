import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../models.dart';
import '../services/api_client.dart';
import '../widgets/common.dart';
import 'result_screen.dart';

/// UI-5: Diagnosis history (FR-10). Search by disease name or by date
/// (YYYY-MM-DD), filter by crop and by All / Confirmed / Uncertain.
class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final _search = TextEditingController();
  String? _status; // null = all
  String? _crop; // null = all crops
  late Future<List<Diagnosis>> _items = _fetch();

  static final _date = RegExp(r'^\d{4}-\d{2}-\d{2}$');

  Future<List<Diagnosis>> _fetch() {
    final text = _search.text.trim();
    final isDate = _date.hasMatch(text);
    return context.read<ApiClient>().history(
          status: _status,
          crop: _crop,
          q: isDate ? null : text,
          dateFrom: isDate ? text : null,
          dateTo: isDate ? text : null,
        );
  }

  void _reload() => setState(() {
        _items = _fetch();
      });

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnosis history')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: TextField(
            key: const Key('search'),
            controller: _search,
            textInputAction: TextInputAction.search,
            decoration: const InputDecoration(
              hintText: 'Search by disease or date (YYYY-MM-DD)',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
            onSubmitted: (_) => _reload(),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: DropdownButtonFormField<String?>(
            key: const Key('cropFilter'),
            initialValue: _crop,
            decoration: const InputDecoration(
                labelText: 'Crop', border: OutlineInputBorder(), isDense: true),
            items: [
              const DropdownMenuItem(value: null, child: Text('All crops')),
              for (final e in cropLabels.entries) DropdownMenuItem(value: e.key, child: Text(e.value)),
            ],
            onChanged: (crop) {
              _crop = crop;
              _reload();
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          // No tick icon and one line per label: on a narrow phone with a large
          // font the labels broke mid-word ("Confirm/ed"). The selected one
          // is still shown by its colour.
          child: SegmentedButton<String?>(
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: null, label: _FilterLabel('All')),
              ButtonSegment(value: 'confirmed', label: _FilterLabel('Confirmed')),
              ButtonSegment(value: 'uncertain', label: _FilterLabel('Uncertain')),
            ],
            selected: {_status},
            onSelectionChanged: (s) {
              _status = s.first;
              _reload();
            },
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Diagnosis>>(
            future: _items,
            builder: (context, snap) {
              if (snap.hasError) {
                return Padding(padding: const EdgeInsets.all(16), child: MessageBox('${snap.error}', onTap: _reload));
              }
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final items = snap.data!;
              if (items.isEmpty) {
                return const Padding(padding: EdgeInsets.all(16), child: MessageBox('No diagnoses found.'));
              }
              return RefreshIndicator(
                onRefresh: () async => _reload(),
                child: ListView.builder(
                  padding: const EdgeInsets.all(8),
                  itemCount: items.length,
                  itemBuilder: (context, i) => _HistoryTile(d: items[i], onReturn: _reload),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.d, required this.onReturn});
  final Diagnosis d;
  final VoidCallback onReturn;

  @override
  Widget build(BuildContext context) {
    final detail = d.isUncertain
        ? 'Needs review'
        : 'Confirmed${d.severityLevel != null ? ', ${titleCase(d.severityLevel!)}' : ''}';
    return Card(
      child: ListTile(
        leading: SizedBox(
          width: 56,
          height: 56,
          child: d.imageUrl == null
              ? const Icon(Icons.image_outlined)
              : ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: Image.network(d.imageUrl!, fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => const Icon(Icons.image_outlined)),
                ),
        ),
        title: Text(d.label),
        subtitle: Text('${formatDate(d.capturedAt)}, ${cropName(d.cropType)}\n$detail'),
        isThreeLine: true,
        trailing: d.isUncertain ? const Icon(Icons.help_outline, color: Colors.orange) : null,
        onTap: () async {
          await Navigator.of(context)
              .push(MaterialPageRoute(builder: (_) => ResultScreen(diagnosisId: d.diagnosisId)));
          onReturn();
        },
      ),
    );
  }
}

/// Status filter label kept on one line; it shrinks a little instead of
/// breaking mid-word when the phone's font size is large.
class _FilterLabel extends StatelessWidget {
  const _FilterLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) =>
      FittedBox(fit: BoxFit.scaleDown, child: Text(text, maxLines: 1, softWrap: false));
}
