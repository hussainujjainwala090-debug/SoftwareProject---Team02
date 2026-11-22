import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../models.dart';
import '../services/api_client.dart';
import '../state/session.dart';
import '../widgets/common.dart';

/// UI-8: Admin knowledge base and user management (FR-17, FR-18).
/// Tabs: Knowledge base, Users, Reports (model accuracy from feedback).
/// Entries used by saved diagnoses are archived, never deleted.
class AdminScreen extends StatelessWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Admin'),
          bottom: const TabBar(tabs: [Tab(text: 'Knowledge base'), Tab(text: 'Users'), Tab(text: 'Reports')]),
        ),
        body: const TabBarView(children: [_KnowledgeBaseTab(), _UsersTab(), _AccuracyTab()]),
      ),
    );
  }
}

// ------------------------------------------------------------ knowledge base ----
class _KnowledgeBaseTab extends StatefulWidget {
  const _KnowledgeBaseTab();

  @override
  State<_KnowledgeBaseTab> createState() => _KnowledgeBaseTabState();
}

class _KnowledgeBaseTabState extends State<_KnowledgeBaseTab> {
  final _search = TextEditingController();
  late Future<List<Disease>> _items = _fetch();

  Future<List<Disease>> _fetch() =>
      context.read<ApiClient>().diseases(q: _search.text.trim(), includeArchived: true);

  void _reload() => setState(() {
        _items = _fetch();
      });

  Future<void> _edit([Disease? d]) async {
    final saved = await showDialog<bool>(context: context, builder: (_) => DiseaseForm(disease: d));
    if (saved == true) _reload();
  }

  Future<void> _toggleArchive(Disease d) async {
    final r = await runWithError(context, () => context.read<ApiClient>().setArchived(d.diseaseId, !d.archived));
    if (r != null) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Expanded(
            child: TextField(
              controller: _search,
              decoration: const InputDecoration(
                  hintText: 'Search diseases', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
              onSubmitted: (_) => _reload(),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            style: FilledButton.styleFrom(minimumSize: const Size(0, 52)),
            icon: const Icon(Icons.add),
            label: const Text('Add disease'),
            onPressed: () => _edit(),
          ),
        ]),
      ),
      Expanded(
        child: FutureBuilder<List<Disease>>(
          future: _items,
          builder: (context, snap) {
            if (snap.hasError) return MessageBox('${snap.error}');
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            return ListView(children: [
              for (final d in snap.data!)
                ListTile(
                  title: Text(d.name),
                  subtitle: Text('${cropName(d.cropType)} · ${d.archived ? 'Archived' : 'Active'} · '
                      '${d.treatments.length} treatments'),
                  trailing: Wrap(children: [
                    TextButton(onPressed: () => _edit(d), child: const Text('Edit')),
                    TextButton(
                        onPressed: () => _toggleArchive(d), child: Text(d.archived ? 'Restore' : 'Archive')),
                  ]),
                ),
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Entries used by saved diagnoses are archived instead of being deleted.'),
              ),
            ]);
          },
        ),
      ),
    ]);
  }
}

/// UI-8 items 5-6: add or edit a disease with its treatments. Entries are
/// validated before saving (SD-3).
class DiseaseForm extends StatefulWidget {
  const DiseaseForm({super.key, this.disease});
  final Disease? disease;

  @override
  State<DiseaseForm> createState() => _DiseaseFormState();
}

class _TreatmentFields {
  _TreatmentFields([Treatment? t])
      : type = t?.type ?? 'organic',
        guidance = TextEditingController(text: t?.guidance),
        warning = TextEditingController(text: t?.safetyWarning);
  String type;
  final TextEditingController guidance;
  final TextEditingController warning;
}

class _DiseaseFormState extends State<DiseaseForm> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.disease?.name);
  late final _symptoms = TextEditingController(text: widget.disease?.symptoms);
  late String _crop = widget.disease?.cropType ?? 'tomato';
  late final List<_TreatmentFields> _treatments = [
    for (final t in widget.disease?.treatments ?? <Treatment>[]) _TreatmentFields(t),
  ];
  String? _error;

  String? _required(String? v) => (v == null || v.trim().isEmpty) ? 'Required' : null;

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final api = context.read<ApiClient>();
    final treatments = [
      for (final t in _treatments)
        Treatment(type: t.type, guidance: t.guidance.text.trim(), safetyWarning: t.warning.text.trim()),
    ];
    final symptoms = _symptoms.text.trim().isEmpty ? null : _symptoms.text.trim();
    try {
      if (widget.disease == null) {
        await api.createDisease(_name.text.trim(), _crop, symptoms, treatments);
      } else {
        await api.updateDisease(widget.disease!.diseaseId, _name.text.trim(), _crop, symptoms, treatments);
      }
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.disease == null ? 'Add disease' : 'Edit entry'),
      content: SizedBox(
        width: 480,
        child: Form(
          key: _form,
          child: ListView(shrinkWrap: true, children: [
            TextFormField(
              key: const Key('diseaseName'),
              controller: _name,
              decoration: const InputDecoration(labelText: 'Disease name'),
              validator: _required,
            ),
            DropdownButtonFormField<String>(
              initialValue: _crop,
              decoration: const InputDecoration(labelText: 'Crop'),
              items: [for (final e in cropLabels.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
              onChanged: (v) => setState(() => _crop = v!),
            ),
            TextFormField(
              controller: _symptoms,
              decoration: const InputDecoration(labelText: 'Symptoms'),
              maxLines: 2,
            ),
            const SizedBox(height: 12),
            Text('Treatments', style: Theme.of(context).textTheme.titleSmall),
            for (final t in _treatments)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Column(children: [
                    Row(children: [
                      Expanded(
                        child: DropdownButtonFormField<String>(
                          initialValue: t.type,
                          items: [
                            for (final type in ['organic', 'chemical', 'preventive'])
                              DropdownMenuItem(value: type, child: Text(titleCase(type))),
                          ],
                          onChanged: (v) => setState(() => t.type = v!),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Remove treatment',
                        icon: const Icon(Icons.close),
                        onPressed: () => setState(() => _treatments.remove(t)),
                      ),
                    ]),
                    TextFormField(
                        controller: t.guidance,
                        decoration: const InputDecoration(labelText: 'Guidance'),
                        validator: _required),
                    TextFormField(
                        controller: t.warning,
                        decoration: const InputDecoration(labelText: 'Safety warning'),
                        validator: _required),
                  ]),
                ),
              ),
            TextButton.icon(
              icon: const Icon(Icons.add),
              label: const Text('Add treatment'),
              onPressed: () => setState(() => _treatments.add(_TreatmentFields())),
            ),
            if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
        FilledButton(
          style: FilledButton.styleFrom(minimumSize: const Size(88, 40)),
          onPressed: _save,
          child: const Text('Save'),
        ),
      ],
    );
  }
}

// --------------------------------------------------------------------- users ----
class _UsersTab extends StatefulWidget {
  const _UsersTab();

  @override
  State<_UsersTab> createState() => _UsersTabState();
}

class _UsersTabState extends State<_UsersTab> {
  late Future<List<AppUser>> _users = context.read<ApiClient>().users();

  void _reload() => setState(() {
        _users = context.read<ApiClient>().users();
      });

  Future<void> _act(Future<Object?> Function() action) async {
    final done = await runWithError(context, () async {
      await action();
      return true;
    });
    if (done == true) _reload();
  }

  Future<void> _changeRole(AppUser u) async {
    final role = await showDialog<String>(
      context: context,
      builder: (_) => SimpleDialog(title: Text('Role for ${u.name}'), children: [
        for (final e in roleLabels.entries)
          SimpleDialogOption(onPressed: () => Navigator.of(context).pop(e.key), child: Text(e.value)),
      ]),
    );
    if (role != null && role != u.role) await _act(() => context.read<ApiClient>().changeRole(u.userId, role));
  }

  Future<void> _remove(AppUser u) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Remove ${u.name}?'),
        content: const Text('The account is deleted and cannot sign in again. '
            'Their farms and saved diagnoses are kept as history.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.of(context).pop(true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok == true && mounted) await _act(() => context.read<ApiClient>().removeUser(u.userId));
  }

  @override
  Widget build(BuildContext context) {
    final me = context.watch<Session>().user!;
    final api = context.read<ApiClient>();
    return FutureBuilder<List<AppUser>>(
      future: _users,
      builder: (context, snap) {
        if (snap.hasError) return MessageBox('${snap.error}');
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        return ListView(children: [
          for (final u in snap.data!)
            ListTile(
              title: Text(u.name),
              subtitle: Text('${roleLabels[u.role]} · ${u.disabled ? 'Disabled' : 'Active'}\n${u.email}'),
              isThreeLine: true,
              trailing: u.userId == me.userId
                  ? const Text('You')
                  : PopupMenuButton<String>(
                      onSelected: (action) => switch (action) {
                        'role' => _changeRole(u),
                        'toggle' => _act(() => api.setDisabled(u.userId, !u.disabled)),
                        _ => _remove(u),
                      },
                      itemBuilder: (_) => [
                        const PopupMenuItem(value: 'role', child: Text('Change role')),
                        PopupMenuItem(value: 'toggle', child: Text(u.disabled ? 'Enable' : 'Disable')),
                        const PopupMenuItem(value: 'remove', child: Text('Remove')),
                      ],
                    ),
            ),
        ]);
      },
    );
  }
}

// ------------------------------------------------------------------ reports ----
class _AccuracyTab extends StatelessWidget {
  const _AccuracyTab();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ModelAccuracy>(
      future: context.read<ApiClient>().modelAccuracy(),
      builder: (context, snap) {
        if (snap.hasError) return MessageBox('${snap.error}');
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final a = snap.data!;
        return ListView(padding: const EdgeInsets.all(16), children: [
          InfoCard(
            title: 'Model accuracy from farmer feedback',
            child: Text(a.overallAccuracy == null
                ? 'No feedback yet.'
                : '${(a.overallAccuracy! * 100).toStringAsFixed(1)}% correct '
                    '(${a.totalFeedback} answers)'),
          ),
          for (final w in a.weeks)
            ListTile(
              title: Text(w.week),
              subtitle: LinearProgressIndicator(value: w.accuracy, minHeight: 8),
              trailing: Text('${(w.accuracy * 100).round()}% of ${w.feedback}'),
            ),
        ]);
      },
    );
  }
}
