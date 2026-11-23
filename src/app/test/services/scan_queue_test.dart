// TC-12 (FR-12) and TC-25 (NFR-08): offline queue on a real SQLite database.
import 'dart:typed_data';

import 'package:agriscan/models.dart';
import 'package:agriscan/services/api_client.dart';
import 'package:agriscan/services/scan_queue.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Diagnosis fakeDiagnosis(String id) => Diagnosis(
      diagnosisId: id, farmId: 'f1', cropType: 'tomato', capturedAt: DateTime.utc(2026, 11, 21),
      label: 'Tomato early blight', status: 'confirmed', confidence: 0.9);

/// Uploader whose behaviour each test sets: online, offline or a server refusal.
class FakeServer {
  Object? error; // ApiException to throw, or null for success
  final uploaded = <String>[];

  Future<Diagnosis> upload(QueuedScan scan) async {
    if (error != null) throw error!;
    uploaded.add(scan.scanId);
    return fakeDiagnosis(scan.scanId);
  }
}

void main() {
  sqfliteFfiInit();
  late SqliteQueueStore store;
  late FakeServer server;
  late ScanQueue queue;
  final jpeg = Uint8List.fromList([0xFF, 0xD8, 1, 2, 3]);

  setUp(() async {
    store = await SqliteQueueStore.open(inMemoryDatabasePath, factory: databaseFactoryFfi,
        singleInstance: false); // a fresh database for every test
    server = FakeServer();
    queue = ScanQueue(store, server.upload);
    await queue.load();
  });

  test('scan taken offline stays pending with its own id and capture time', () async {
    server.error = ApiException(null, 'Cannot reach the server.');
    final taken = DateTime.utc(2026, 11, 20, 8);
    final scan = await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg, capturedAt: taken);

    final result = await queue.sync(scan.scanId);
    expect(result.waiting, isTrue);
    final stored = (await store.all()).single;
    expect(stored.status, QueueStatus.pending);
    expect(stored.capturedAt, taken);
    expect(stored.error, 'Waiting for connection');
    expect(stored.scanId, matches(RegExp(r'^[0-9a-f]{32}$')));
  });

  test('pending scans upload when the connection returns and leave the queue', () async {
    server.error = ApiException(null, 'offline');
    await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg);
    await queue.enqueue(farmId: 'f1', cropType: 'pepper', jpeg: jpeg);
    expect(await queue.syncAll(), 0);
    expect(queue.pendingCount, 2);

    server.error = null;
    expect(await queue.syncAll(), 2);
    expect(queue.items, isEmpty);
    expect(await store.all(), isEmpty);
  });

  test('a scan the server refuses is marked failed with the server message', () async {
    server.error = ApiException(422, 'Image is blurry. Please retake.');
    final scan = await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg);
    final result = await queue.sync(scan.scanId);
    expect(result.waiting, isFalse);
    expect(queue.items.single.status, QueueStatus.failed);
    expect(queue.items.single.error, 'Image is blurry. Please retake.');
    expect(queue.failedCount, 1);

    // Failed scans are skipped by the automatic sync, but "Retry" sends them again.
    server.error = null;
    expect(await queue.syncAll(), 0);
    expect(await queue.syncAll(includeFailed: true), 1);
  });

  test('server errors (5xx) and expired sign-in stay retryable', () async {
    for (final e in [ApiException(503, 'down'), ApiException(401, 'Invalid or expired token')]) {
      server.error = e;
      final scan = await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg);
      await queue.sync(scan.scanId);
      expect(queue.items.last.status, QueueStatus.pending);
    }
  });

  test('a retry sends the same scan_id, so the backend cannot duplicate it', () async {
    server.error = ApiException(null, 'offline');
    final scan = await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg);
    await queue.sync(scan.scanId);
    await queue.sync(scan.scanId);
    server.error = null;
    await queue.sync(scan.scanId);
    expect(server.uploaded, [scan.scanId]);
  });

  test('uploads cut off by closing the app go back to pending on start-up', () async {
    final scan = QueuedScan(scanId: 'a' * 32, farmId: 'f1', cropType: 'tomato',
        capturedAt: DateTime.utc(2026, 11, 21), image: jpeg, status: QueueStatus.syncing);
    await store.insert(scan);
    final restarted = ScanQueue(store, server.upload);
    await restarted.load();
    expect(restarted.items.single.status, QueueStatus.pending);
  });

  test('the database refuses a second row with the same scan_id', () async {
    final scan = await queue.enqueue(farmId: 'f1', cropType: 'tomato', jpeg: jpeg);
    expect(() => store.insert(scan), throwsA(isA<DatabaseException>()));
  });
}
