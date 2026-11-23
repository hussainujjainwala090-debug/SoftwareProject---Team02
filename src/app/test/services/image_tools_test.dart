// TC-03 (FR-03) and TC-20 (NFR-02): on-phone blur check and compression to 1 MB or less.
import 'dart:math';
import 'dart:typed_data';

import 'package:agriscan/services/image_tools.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

/// Leaf-like photo: green ellipse with brown spots and camera noise.
img.Image leaf(int w, int h, {int seed = 1}) {
  final r = Random(seed);
  final image = img.Image(width: w, height: h);
  for (var y = 0; y < h; y++) {
    for (var x = 0; x < w; x++) {
      final dx = (x - w / 2) / (w * 0.4), dy = (y - h / 2) / (h * 0.3);
      final inLeaf = dx * dx + dy * dy <= 1;
      final spot = pow(x - w * 0.4, 2) + pow(y - h * 0.45, 2) < pow(w * 0.06, 2);
      final base = !inLeaf ? [125, 125, 125] : (spot ? [125, 70, 25] : [55, 145, 45]);
      int n(int v) => (v + r.nextInt(41) - 20).clamp(0, 255);
      image.setPixelRgb(x, y, n(base[0]), n(base[1]), n(base[2]));
    }
  }
  return image;
}

void main() {
  test('a sharp leaf photo passes', () {
    final result = checkQuality(Uint8List.fromList(img.encodePng(leaf(256, 256))));
    expect(result.ok, isTrue, reason: 'score ${result.blurScore}');
  });

  test('a blurred photo asks for a retake', () {
    final blurred = img.gaussianBlur(leaf(256, 256), radius: 6);
    final result = checkQuality(Uint8List.fromList(img.encodePng(blurred)));
    expect(result.ok, isFalse);
    expect(result.message, 'Image is blurry. Please retake.');
  });

  test('a dark photo asks for better light', () {
    final dark = img.Image(width: 200, height: 200)..clear(img.ColorRgb8(10, 10, 10));
    final result = checkQuality(Uint8List.fromList(img.encodePng(dark)));
    expect(result.ok, isFalse);
    expect(result.message, contains('too dark'));
  });

  test('a non-image file is refused', () {
    expect(checkQuality(Uint8List.fromList([1, 2, 3])).ok, isFalse);
  });

  test('NFR-02: a 10 MB camera photo is compressed to 1 MB or less and stays sharp', () {
    // 4000 x 3000 noisy photo saved at maximum JPEG quality, like a phone camera file.
    final big = Uint8List.fromList(img.encodeJpg(leaf(4000, 3000), quality: 100));
    expect(big.length, greaterThan(8000000));
    final small = compressForUpload(big);
    expect(small.length, lessThanOrEqualTo(1000000));
    final decoded = img.decodeJpg(small)!;
    expect(decoded.width, 1600);
    expect(checkQuality(small).ok, isTrue);
  }, timeout: const Timeout(Duration(minutes: 3)));
}
