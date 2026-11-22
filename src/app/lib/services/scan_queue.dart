import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';

import '../models.dart';
import 'api_client.dart';

/// Offline queue (FR-12, NFR-08; "Local SQLite queue" in ARCH-1).
///
/// Every scan goes through this queue, online or not. The scan_id and the
/// capture time are created on the phone and stored with the photo, so the
/// backend returns the same diagnosis if an upload is retried. Diagnosis needs
/// a connection: queued scans are diagnosed when they upload.
enum QueueStatus { pending, syncing, failed }

class QueuedScan {
  QueuedScan({
    required this.scanId,
    required this.farmId,
    required this.cropType,
    required this.capturedAt,
    required this.image,
    this.status = QueueStatus.pending,
    this.error,
    this.attempts = 0,
  });

  final String scanId;
  final String farmId;
  final String cropType;
  final DateTime capturedAt;
  final Uint8List image;
  QueueStatus status;
  String? error;
  int attempts;

  Map<String, Object?> toRow() => {
        'scan_id': scanId,
        'farm_id': farmId,
        'crop_type': cropType,
        'captured_at': capturedAt.toUtc().toIso8601String(),
        'image': image,
        'status': status.name,
        'error': error,
        'attempts': attempts,
      };

  factory QueuedScan.fromRow(Map<String, Object?> r) => QueuedScan(
        scanId: r['scan_id'] as String,
        farmId: r['farm_id'] as String,
        cropType: r['crop_type'] as String,
        capturedAt: DateTime.parse(r['captured_at'] as String),
        image: r['image'] as Uint8List,
        status: QueueStatus.values.byName(r['status'] as String),
        error: r['error'] as String?,
        attempts: r['attempts'] as int,
      );
}

abstract class QueueStore {
  Future<List<QueuedScan>> all();
  Future<void> insert(QueuedScan scan);
  Future<void> save(QueuedScan scan);
  Future<void> delete(String scanId);
}

class SqliteQueueStore implements QueueStore {
  SqliteQueueStore(this._db);
  final Database _db;

  static Future<SqliteQueueStore> open(String path, {DatabaseFactory? factory,
      bool singleInstance = true}) async {
    final db = await (factory ?? databaseFactory).openDatabase(path,
        options: OpenDatabaseOptions(
          version: 1,
          singleInstance: singleInstance,
          onCreate: (db, _) => db.execute('''
            CREATE TABLE queued_scans (
              scan_id TEXT PRIMARY KEY,
              farm_id TEXT NOT NULL,
              crop_type TEXT NOT NULL,
              captured_at TEXT NOT NULL,
              image BLOB NOT NULL,
              status TEXT NOT NULL CHECK (status IN ('pending', 'syncing', 'failed')),
              error TEXT,
              attempts INTEGER NOT NULL DEFAULT 0
            )'''),
        ));
    return SqliteQueueStore(db);
  }

  @override
  Future<List<QueuedScan>> all() async =>
      (await _db.query('queued_scans', orderBy: 'captured_at')).map(QueuedScan.fromRow).toList();

  @override
  Future<void> insert(QueuedScan scan) => _db.insert('queued_scans', scan.toRow());

  @override
  Future<void> save(QueuedScan scan) =>
      _db.update('queued_scans', scan.toRow(), where: 'scan_id = ?', whereArgs: [scan.scanId]);

  @override
  Future<void> delete(String scanId) =>
      _db.delete('queued_scans', where: 'scan_id = ?', whereArgs: [scanId]);
}

/// In-memory store for the browser preview and widget tests (not persistent).
class MemoryQueueStore implements QueueStore {
  final _rows = <String, Map<String, Object?>>{};

  @override
  Future<List<QueuedScan>> all() async => _rows.values.map(QueuedScan.fromRow).toList()
    ..sort((a, b) => a.capturedAt.compareTo(b.capturedAt));

  @override
  Future<void> insert(QueuedScan scan) async {
    if (_rows.containsKey(scan.scanId)) throw StateError('duplicate scan_id');
    _rows[scan.scanId] = scan.toRow();
  }

  @override
  Future<void> save(QueuedScan scan) async => _rows[scan.scanId] = scan.toRow();

  @override
  Future<void> delete(String scanId) async => _rows.remove(scanId);
}

typedef Uploader = Future<Diagnosis> Function(QueuedScan scan);

/// Result of trying to send one queued scan.
class SyncResult {
  const SyncResult.done(this.diagnosis) : error = null, waiting = false;
  const SyncResult.waiting(this.error) : diagnosis = null, waiting = true;
  const SyncResult.failed(this.error) : diagnosis = null, waiting = false;
  final Diagnosis? diagnosis;
  final String? error;
  final bool waiting; // kept as pending: no connection or server error
}

String newScanId([Random? random]) {
  final r = random ?? Random.secure();
  return List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
}

class ScanQueue extends ChangeNotifier {
  ScanQueue(this._store, this._upload);

  final QueueStore _store;
  final Uploader _upload;
  List<QueuedScan> _items = [];
  bool _syncingAll = false;

  List<QueuedScan> get items => List.unmodifiable(_items);
  int get pendingCount => _items.where((s) => s.status != QueueStatus.failed).length;
  int get failedCount => _items.where((s) => s.status == QueueStatus.failed).length;

  /// Load the queue; uploads interrupted by closing the app go back to pending.
  Future<void> load() async {
    _items = await _store.all();
    for (final s in _items.where((s) => s.status == QueueStatus.syncing)) {
      s.status = QueueStatus.pending;
      await _store.save(s);
    }
    notifyListeners();
  }

  Future<QueuedScan> enqueue({required String farmId, required String cropType, required Uint8List jpeg,
      DateTime? capturedAt}) async {
    final scan = QueuedScan(scanId: newScanId(), farmId: farmId, cropType: cropType,
        capturedAt: (capturedAt ?? DateTime.now()).toUtc(), image: jpeg);
    await _store.insert(scan);
    _items = [..._items, scan];
    notifyListeners();
    return scan;
  }

  Future<SyncResult> sync(String scanId) async {
    final scan = _items.firstWhere((s) => s.scanId == scanId);
    scan
      ..status = QueueStatus.syncing
      ..attempts += 1;
    await _store.save(scan);
    notifyListeners();
    SyncResult result;
    try {
      final diagnosis = await _upload(scan);
      await _store.delete(scanId);
      _items = _items.where((s) => s.scanId != scanId).toList();
      result = SyncResult.done(diagnosis);
    } on ApiException catch (e) {
      if (e.isRetryable || e.isUnauthorized) {
        scan
          ..status = QueueStatus.pending
          ..error = e.isNetwork ? 'Waiting for connection' : e.message;
        result = SyncResult.waiting(scan.error);
      } else {
        scan
          ..status = QueueStatus.failed
          ..error = e.message; // e.g. "Image is blurry. Please retake."
        result = SyncResult.failed(e.message);
      }
      await _store.save(scan);
    }
    notifyListeners();
    return result;
  }

  /// Send every pending scan (on start-up, when the connection returns, or on "Retry").
  Future<int> syncAll({bool includeFailed = false}) async {
    if (_syncingAll) return 0;
    _syncingAll = true;
    var sent = 0;
    try {
      for (final scan in List.of(_items)) {
        if (scan.status == QueueStatus.failed && !includeFailed) continue;
        final r = await sync(scan.scanId);
        if (r.diagnosis != null) sent++;
        if (r.waiting && r.error == 'Waiting for connection') break; // still offline
      }
    } finally {
      _syncingAll = false;
    }
    return sent;
  }

  Future<void> discard(String scanId) async {
    await _store.delete(scanId);
    _items = _items.where((s) => s.scanId != scanId).toList();
    notifyListeners();
  }
}
