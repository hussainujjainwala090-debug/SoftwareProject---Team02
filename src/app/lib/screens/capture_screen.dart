import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../services/image_tools.dart';
import '../services/scan_queue.dart';
import '../state/session.dart';
import '../widgets/common.dart';
import 'farm_profile_screen.dart';
import 'result_screen.dart';

typedef ImageSourceFn = Future<Uint8List?> Function();

/// Runs in a background isolate: quality check, then compression to <= 1 MB.
({String? error, Uint8List? jpeg}) prepareImage(Uint8List bytes) {
  final q = checkQuality(bytes);
  if (!q.ok) return (error: q.message, jpeg: null);
  return (error: null, jpeg: compressForUpload(bytes));
}

/// UI-3: Capture leaf image (FR-03, FR-12). Photos are checked for blur and
/// light on the phone, compressed, and always go through the offline queue.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, this.useCamera = true, this.pickFromGallery});

  /// Widget tests run without a camera.
  final bool useCamera;
  final ImageSourceFn? pickFromGallery;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _camera;
  String? _crop;
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    if (widget.useCamera) _startCamera();
  }

  Future<void> _startCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;
      final back = cameras.firstWhere((c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => cameras.first);
      final controller = CameraController(back, ResolutionPreset.high, enableAudio: false);
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _camera = controller);
    } on Object catch (e) {
      debugPrint('Camera not available: $e');
    }
  }

  @override
  void dispose() {
    _camera?.dispose();
    super.dispose();
  }

  Future<void> _capture() async {
    final cam = _camera;
    if (cam == null || !cam.value.isInitialized) {
      setState(() => _message = 'No camera found. Use Gallery to pick a photo.');
      return;
    }
    final file = await cam.takePicture();
    await _handle(await file.readAsBytes());
  }

  Future<void> _gallery() async {
    final pick = widget.pickFromGallery ??
        () async => (await ImagePicker().pickImage(source: ImageSource.gallery))?.readAsBytes();
    final bytes = await pick();
    if (bytes != null) await _handle(bytes);
  }

  Future<void> _handle(Uint8List bytes) async {
    final session = context.read<Session>();
    final queue = context.read<ScanQueue>();
    final farm = session.selectedFarm!;
    final crop = _crop ?? farm.crops.first;
    setState(() {
      _busy = true;
      _message = 'Checking the photo...';
    });
    try {
      final prepared = await compute(prepareImage, bytes);
      if (prepared.error != null) {
        setState(() => _message = prepared.error);
        return;
      }
      final scan = await queue.enqueue(farmId: farm.farmId, cropType: crop, jpeg: prepared.jpeg!);
      setState(() => _message = 'Sending for diagnosis...');
      final result = await queue.sync(scan.scanId);
      if (!mounted) return;
      if (result.diagnosis != null) {
        setState(() => _message = null);
        await Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => ResultScreen(diagnosisId: result.diagnosis!.diagnosisId)));
      } else if (result.waiting) {
        setState(() => _message = 'No connection. The scan is saved and will be sent when you are online.');
      } else {
        setState(() => _message = result.error);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<Session>();
    final queue = context.watch<ScanQueue>();
    final farm = session.selectedFarm;
    if (farm == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('New scan')),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Text('Create your farm profile first, so scans know the crop and location.',
                textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () =>
                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => const FarmProfileScreen())),
              child: const Text('Create farm profile'),
            ),
          ]),
        ),
      );
    }
    final crop = farm.crops.contains(_crop) ? _crop! : farm.crops.first;
    final blurry = _message != null && (_message!.contains('blurry') || _message!.contains('dark'));
    return Scaffold(
      appBar: AppBar(title: const Text('New scan')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (session.farms.length > 1)
          DropdownButtonFormField<String>(
            initialValue: farm.farmId,
            decoration: const InputDecoration(labelText: 'Farm', border: OutlineInputBorder()),
            isExpanded: true, // long farm names end in "..." instead of overflowing
            items: [
              for (final f in session.farms)
                DropdownMenuItem(value: f.farmId, child: Text(f.name, overflow: TextOverflow.ellipsis)),
            ],
            onChanged: (id) => session.selectFarm(id!),
          ),
        if (session.farms.length > 1) const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: const Key('crop'),
          initialValue: crop,
          decoration: const InputDecoration(labelText: 'Crop', border: OutlineInputBorder()),
          items: [for (final c in farm.crops) DropdownMenuItem(value: c, child: Text(cropName(c)))],
          onChanged: (c) => setState(() => _crop = c),
        ),
        const SizedBox(height: 12),
        AspectRatio(
          aspectRatio: 3 / 4,
          child: Stack(fit: StackFit.expand, children: [
            Container(
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(12),
              ),
              clipBehavior: Clip.antiAlias,
              child: _camera != null && _camera!.value.isInitialized ? CameraPreview(_camera!) : null,
            ),
            // Guide frame for leaf placement (UI-3 item 3).
            Center(
              child: FractionallySizedBox(
                widthFactor: 0.75,
                heightFactor: 0.6,
                child: Container(
                  alignment: Alignment.bottomCenter,
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(border: Border.all(color: Colors.white, width: 2)),
                  child: const Text('Place the leaf inside this frame',
                      style: TextStyle(color: Colors.white, backgroundColor: Colors.black45)),
                ),
              ),
            ),
          ]),
        ),
        const SizedBox(height: 12),
        if (_message != null)
          MessageBox(_message!,
              icon: blurry ? Icons.warning_amber : Icons.info_outline,
              color: blurry ? Theme.of(context).colorScheme.error : null),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
            child: OutlinedButton.icon(
              icon: const Icon(Icons.photo_library_outlined),
              label: const Text('Gallery'),
              onPressed: _busy ? null : _gallery,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: FilledButton.icon(
              icon: const Icon(Icons.camera),
              label: const Text('Capture'),
              onPressed: _busy ? null : _capture,
            ),
          ),
        ]),
        const SizedBox(height: 16),
        if (queue.items.isNotEmpty) _QueueNote(queue: queue),
      ]),
    );
  }
}

/// UI-3 item 7: scans waiting in the offline queue, with retry.
class _QueueNote extends StatelessWidget {
  const _QueueNote({required this.queue});
  final ScanQueue queue;

  @override
  Widget build(BuildContext context) {
    final parts = [
      if (queue.pendingCount > 0) '${queue.pendingCount} scan${queue.pendingCount == 1 ? '' : 's'} pending',
      if (queue.failedCount > 0) '${queue.failedCount} failed',
    ];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      MessageBox('Offline queue: ${parts.join(', ')}. Tap to retry.',
          icon: Icons.cloud_upload_outlined, onTap: () => queue.syncAll(includeFailed: true)),
      for (final s in queue.items)
        ListTile(
          dense: true,
          leading: Icon(switch (s.status) {
            QueueStatus.pending => Icons.schedule,
            QueueStatus.syncing => Icons.sync,
            QueueStatus.failed => Icons.error_outline,
          }),
          title: Text('${cropName(s.cropType)}, ${formatDate(s.capturedAt)}: ${s.status.name}'),
          subtitle: s.error == null ? null : Text(s.error!),
          trailing: s.status == QueueStatus.failed
              ? IconButton(
                  tooltip: 'Remove',
                  icon: const Icon(Icons.delete_outline),
                  onPressed: () => queue.discard(s.scanId),
                )
              : null,
        ),
    ]);
  }
}
