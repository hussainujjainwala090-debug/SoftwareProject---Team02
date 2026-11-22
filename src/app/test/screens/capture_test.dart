// TC-03 (FR-03) and TC-12 (FR-12): capture screen with on-phone checks and the offline queue.
import 'dart:math';
import 'dart:typed_data';

import 'package:agriscan/screens/capture_screen.dart';
import 'package:agriscan/screens/result_screen.dart';
import 'package:agriscan/services/scan_queue.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:image/image.dart' as img;

import '../helpers.dart';

Uint8List leafPhoto({double blur = 0}) {
  final r = Random(3);
  var image = img.Image(width: 320, height: 320);
  for (var y = 0; y < 320; y++) {
    for (var x = 0; x < 320; x++) {
      final inLeaf = pow((x - 160) / 120, 2) + pow((y - 160) / 90, 2) <= 1;
      final v = r.nextInt(41) - 20;
      image.setPixelRgb(x, y, (inLeaf ? 55 : 125) + v, (inLeaf ? 145 : 125) + v, (inLeaf ? 45 : 125) + v);
    }
  }
  if (blur > 0) image = img.gaussianBlur(image, radius: blur.round());
  return Uint8List.fromList(img.encodeJpg(image, quality: 92));
}

void main() {
  Future<TestApp> showCapture(WidgetTester tester, Uint8List photo) async {
    final app = TestApp();
    await app.show(tester, CaptureScreen(useCamera: false, pickFromGallery: () async => photo));
    return app;
  }

  Future<void> pickAndWait(WidgetTester tester) async {
    await tester.tap(find.text('Gallery'));
    // Image checks run in a background isolate, so let real time pass.
    await tester.runAsync(() => Future<void>.delayed(const Duration(seconds: 2)));
    await tester.pumpAndSettle();
  }

  testWidgets('shows the farm crops, guide frame, gallery and capture buttons', (tester) async {
    await showCapture(tester, leafPhoto());
    expect(find.text('Place the leaf inside this frame'), findsOneWidget);
    expect(find.text('Date palm'), findsOneWidget); // first crop of the farm
    expect(find.text('Gallery'), findsOneWidget);
    expect(find.text('Capture'), findsOneWidget);
  });

  testWidgets('a blurry photo asks for a retake and is not uploaded', (tester) async {
    final app = await showCapture(tester, leafPhoto(blur: 6));
    await pickAndWait(tester);
    expect(find.text('Image is blurry. Please retake.'), findsOneWidget);
    expect(app.backend.sent('POST', '/scans'), isEmpty);
    expect(app.queue.items, isEmpty);
  });

  testWidgets('a good photo is uploaded and the result opens', (tester) async {
    final app = await showCapture(tester, leafPhoto());
    await pickAndWait(tester);
    final upload = app.backend.sent('POST', '/scans');
    expect(upload, hasLength(1));
    expect(upload.single.bodyBytes.length, lessThanOrEqualTo(1000000 + 2000));
    expect(find.byType(ResultScreen), findsOneWidget);
    expect(app.queue.items, isEmpty);
  });

  testWidgets('offline: the scan is kept as pending and shown in the queue note', (tester) async {
    final app = TestApp();
    app.backend.overrides['POST /scans'] = (_) => throw http.ClientException('offline');
    await app.show(tester, CaptureScreen(useCamera: false, pickFromGallery: () async => leafPhoto()));
    await pickAndWait(tester);
    expect(find.textContaining('will be sent when you are online'), findsOneWidget);
    expect(app.queue.items.single.status, QueueStatus.pending);
    expect(find.textContaining('1 scan pending'), findsOneWidget);

    // Connection back: tapping the note sends the queued scan.
    app.backend.overrides.remove('POST /scans');
    await tester.tap(find.textContaining('Tap to retry'));
    await tester.pumpAndSettle();
    expect(app.queue.items, isEmpty);
    expect(app.backend.sent('POST', '/scans'), hasLength(2)); // same scan, sent again
  });

  testWidgets('a farmer without a farm is asked to create one first', (tester) async {
    final app = TestApp(withFarm: false);
    await app.show(tester, const CaptureScreen(useCamera: false));
    expect(find.text('Create farm profile'), findsOneWidget);
  });
}
