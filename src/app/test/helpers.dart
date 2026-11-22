// Test helpers: a fake backend that answers with real saved responses
// (test/fixtures, from src/backend/scripts/export_fixtures.py) and records
// every request, plus a way to show one screen with the app's providers.
import 'dart:convert';
import 'dart:io';

import 'package:agriscan/models.dart';
import 'package:agriscan/services/api_client.dart';
import 'package:agriscan/services/auth_service.dart';
import 'package:agriscan/services/scan_queue.dart';
import 'package:agriscan/state/session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

dynamic fixture(String name) => jsonDecode(File('test/fixtures/$name.json').readAsStringSync());

http.Response httpJson(Object? body, [int status = 200]) =>
    http.Response.bytes(utf8.encode(jsonEncode(body)), status, headers: {'content-type': 'application/json'});

/// Scroll the page (its outermost list) until [f] is built, then fully into view.
Future<void> scrollTo(WidgetTester tester, Finder f) async {
  await tester.scrollUntilVisible(f, 300, scrollable: find.byType(Scrollable).first);
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
}

/// The backend's answer for a signed-in account without a Users row.
http.Response http403() =>
    httpJson({'detail': 'Account not registered; call POST /api/v1/users/register'}, 403);

class FakeBackend {
  final requests = <http.Request>[];

  /// Replace the answer for "METHOD /path" (path without /api/v1).
  final overrides = <String, http.Response Function(http.Request)>{};

  late final String confirmedId = (fixture('diagnosis_confirmed') as Map)['diagnosis_id'] as String;
  late final String uncertainId = (fixture('diagnosis_uncertain') as Map)['diagnosis_id'] as String;

  http.Response _json(Object body, [int status = 200]) =>
      http.Response.bytes(utf8.encode(jsonEncode(body)), status, headers: {'content-type': 'application/json'});

  late final MockClient client = MockClient((req) async {
    requests.add(req);
    final path = req.url.path.replaceFirst('/api/v1', '');
    final key = '${req.method} $path';
    if (overrides.containsKey(key)) return overrides[key]!(req);
    final segments = path.split('/')..removeAt(0);
    return switch ((req.method, segments)) {
      ('GET', ['users', 'me']) => _json(fixture('me')),
      ('POST', ['users', 'register']) => _json(fixture('me'), 201),
      ('GET', ['farms']) => _json([fixture('farm')]),
      ('POST', ['farms']) || ('PUT', ['farms', _]) => _json(fixture('farm'), 201),
      ('GET', ['farms', _, 'dashboard']) => _json(fixture('dashboard')),
      ('POST', ['scans']) => _json(fixture('diagnosis_confirmed'), 201),
      ('GET', ['diagnoses']) => _json(fixture('history')),
      ('GET', ['diagnoses', final id]) =>
        _json(fixture(id == uncertainId ? 'diagnosis_uncertain' : 'diagnosis_confirmed')),
      ('GET', ['diagnoses', _, 'spread-risk']) => _json(fixture('spread_risk')),
      ('POST', ['diagnoses', _, 'feedback']) => _json({'feedback_id': 'x', 'diagnosis_id': 'x', 'correct': true}, 201),
      ('POST', ['diagnoses', _, 'review']) => _json(fixture('diagnosis_confirmed')),
      ('POST', ['diagnoses', _, 'reports']) => _json(fixture('report'), 201),
      ('GET', ['diagnoses', _, 'reports']) => _json([fixture('report')]),
      ('GET', ['diseases']) => _json(fixture('diseases')),
      ('GET', ['admin', 'users']) => _json(fixture('users')),
      ('GET', ['admin', 'model-accuracy']) => _json(fixture('model_accuracy')),
      _ => _json({'detail': 'Not found in fake backend: $key'}, 404),
    };
  });

  List<http.Request> sent(String method, String pathPart) =>
      requests.where((r) => r.method == method && r.url.path.contains(pathPart)).toList();
}

class TestApp {
  TestApp({String role = 'farmer', bool withFarm = true}) {
    auth = DevAuthService();
    api = ApiClient(baseUrl: 'http://test', auth: auth, client: backend.client);
    session = Session(api, auth);
    final me = fixture('me') as Map<String, dynamic>;
    session
      ..user = AppUser.fromJson({...me, 'role': role})
      ..farms = withFarm ? [Farm.fromJson(fixture('farm') as Map<String, dynamic>)] : []
      ..status = SessionStatus.ready;
    queue = ScanQueue(MemoryQueueStore(), (s) => api.uploadScan(
        scanId: s.scanId, farmId: s.farmId, cropType: s.cropType, capturedAt: s.capturedAt, jpeg: s.image));
  }

  final backend = FakeBackend();
  late final DevAuthService auth;
  late final ApiClient api;
  late final Session session;
  late final ScanQueue queue;

  Widget wrap(Widget child) => MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: session),
          ChangeNotifierProvider.value(value: queue),
          Provider.value(value: api),
        ],
        child: MaterialApp(home: child),
      );

  Future<void> show(WidgetTester tester, Widget screen) async {
    await auth.signIn('farmer@example.com', 'x');
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.5;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(wrap(screen));
    await tester.pumpAndSettle();
  }
}
