import 'dart:typed_data';

import 'package:image/image.dart' as img;

/// Phone-side image checks (FR-03, NFR-02). They use the same rules as the
/// backend (app/image_quality.py) so the phone never accepts a photo the
/// server would refuse: Laplacian variance on a grey image of at most 512 px,
/// blur threshold 20, mean brightness of at least 40.
const blurThreshold = 20.0;
const minBrightness = 40.0;
const maxUploadBytes = 1000000;

class QualityResult {
  const QualityResult(this.ok, this.message, this.blurScore, this.brightness);
  final bool ok;
  final String? message;
  final double blurScore;
  final double brightness;
}

double laplacianVariance(img.Image grey) {
  final w = grey.width, h = grey.height;
  if (w < 3 || h < 3) return 0;
  final px = List<double>.generate(w * h, (i) => grey.getPixel(i % w, i ~/ w).r.toDouble());
  double sum = 0, sumSq = 0;
  var n = 0;
  for (var y = 1; y < h - 1; y++) {
    for (var x = 1; x < w - 1; x++) {
      final c = px[y * w + x];
      final lap = -4 * c + px[(y - 1) * w + x] + px[(y + 1) * w + x] + px[y * w + x - 1] + px[y * w + x + 1];
      sum += lap;
      sumSq += lap * lap;
      n++;
    }
  }
  final mean = sum / n;
  return sumSq / n - mean * mean;
}

QualityResult checkQuality(Uint8List bytes) {
  final decoded = img.decodeImage(bytes);
  if (decoded == null) return const QualityResult(false, 'This file is not a readable image.', 0, 0);
  var grey = img.grayscale(img.bakeOrientation(decoded));
  if (grey.width > 512 || grey.height > 512) {
    grey = grey.width >= grey.height
        ? img.copyResize(grey, width: 512, interpolation: img.Interpolation.average)
        : img.copyResize(grey, height: 512, interpolation: img.Interpolation.average);
  }
  if (grey.width < 32 || grey.height < 32) {
    return const QualityResult(false, 'The image is too small.', 0, 0);
  }
  double total = 0;
  for (final p in grey) {
    total += p.r;
  }
  final brightness = total / (grey.width * grey.height);
  final score = laplacianVariance(grey);
  if (brightness < minBrightness) {
    return QualityResult(false, 'The image is too dark. Please retake in better light.', score, brightness);
  }
  if (score < blurThreshold) {
    return QualityResult(false, 'Image is blurry. Please retake.', score, brightness);
  }
  return QualityResult(true, null, score, brightness);
}

/// Resize and re-encode as JPEG until the file is at most [maxBytes] (NFR-02).
Uint8List compressForUpload(Uint8List bytes, {int maxBytes = maxUploadBytes, int maxSide = 1600}) {
  final decoded = img.decodeImage(bytes);
  if (decoded == null) throw const FormatException('Not an image');
  var image = img.bakeOrientation(decoded);
  if (image.width > maxSide || image.height > maxSide) {
    image = image.width >= image.height
        ? img.copyResize(image, width: maxSide)
        : img.copyResize(image, height: maxSide);
  }
  var quality = 85;
  var out = img.encodeJpg(image, quality: quality);
  while (out.length > maxBytes) {
    if (quality > 45) {
      quality -= 10;
    } else {
      image = img.copyResize(image, width: (image.width * 0.8).round());
    }
    out = img.encodeJpg(image, quality: quality);
  }
  return out;
}
