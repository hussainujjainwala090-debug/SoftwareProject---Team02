import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../widgets/common.dart';

/// UI-7 / FR-15: PDF reports of a diagnosis. The server builds the PDF in the
/// UI-7 layout; here the farmer opens it or copies the link to share it.
class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, required this.diagnosisId, this.latest});
  final String diagnosisId;
  final Report? latest;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  late Future<List<Report>> _reports = context.read<ApiClient>().reports(widget.diagnosisId);

  Future<void> _open(Report r) async {
    if (!await launchUrl(Uri.parse(r.pdfUrl), mode: LaunchMode.externalApplication) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open the PDF')));
    }
  }

  Future<void> _copy(Report r) async {
    await Clipboard.setData(ClipboardData(text: r.pdfUrl));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Link copied. Paste it in a message to your agronomist.')));
    }
  }

  Future<void> _new() async {
    final r = await runWithError(context, () => context.read<ApiClient>().createReport(widget.diagnosisId));
    if (r != null && mounted) {
      setState(() {
        _reports = context.read<ApiClient>().reports(widget.diagnosisId);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PDF report')),
      body: FutureBuilder<List<Report>>(
        future: _reports,
        builder: (context, snap) {
          if (snap.hasError) return Center(child: MessageBox('${snap.error}'));
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final reports = snap.data!;
          // Bottom padding keeps the last item above Android's navigation bar.
          return ListView(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.paddingOf(context).bottom),
              children: [
            const Text('The report has the farm and crop, the original and highlighted photos, '
                'the results, the treatments and the weather at the time of the scan.'),
            const SizedBox(height: 12),
            for (final r in reports)
              Card(
                child: ListTile(
                  leading: const Icon(Icons.picture_as_pdf, color: Colors.red),
                  title: Text('Report of ${formatDate(r.createdAt)}'),
                  subtitle: Text(r.reportId == widget.latest?.reportId ? 'Just created' : 'Earlier report'),
                  trailing: Wrap(children: [
                    IconButton(tooltip: 'Open', icon: const Icon(Icons.open_in_new), onPressed: () => _open(r)),
                    IconButton(tooltip: 'Copy share link', icon: const Icon(Icons.link), onPressed: () => _copy(r)),
                  ]),
                ),
              ),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: _new, child: const Text('Create a new report')),
          ]);
        },
      ),
    );
  }
}
