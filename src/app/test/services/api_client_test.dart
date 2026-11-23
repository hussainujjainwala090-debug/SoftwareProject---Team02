// API client: bearer token on every request, errors mapped for the queue and screens.
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:agriscan/services/api_client.dart';
import 'package:agriscan/services/auth_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

String fixtureText(String name) => File('test/fixtures/$name.json').readAsStringSync();

void main() {
  late DevAuthService auth;
  setUp(() async {
    auth = DevAuthService();
    await auth.signIn('Aisha@Example.com', 'secret123');
  });

  test('dev token is dev:<uid>:<email> with a uid the backend accepts', () async {
    expect(await auth.idToken(), 'dev:dev-aisha_example_com:aisha@example.com');
  });

  test('every request carries the bearer token and query filters', () async {
    late http.Request seen;
    final api = ApiClient(baseUrl: 'http://api', auth: auth, client: MockClient((req) async {
      seen = req;
      return http.Response(fixtureText('history'), 200);
    }));
    final list = await api.history(status: 'uncertain', q: '', crop: 'tomato');
    expect(list, hasLength(2));
    expect(seen.headers['Authorization'], 'Bearer dev:dev-aisha_example_com:aisha@example.com');
    expect(seen.url.toString(), 'http://api/api/v1/diagnoses?status=uncertain&crop=tomato');
  });

  test('server refusals keep their message; validation errors get a plain one', () async {
    var body = jsonEncode({'detail': 'Image is blurry. Please retake.'});
    var status = 422;
    final api = ApiClient(baseUrl: 'http://api', auth: auth,
        client: MockClient((_) async => http.Response(body, status)));
    await expectLater(api.me(), throwsA(isA<ApiException>()
        .having((e) => e.statusCode, 'status', 422)
        .having((e) => e.message, 'message', 'Image is blurry. Please retake.')
        .having((e) => e.isRetryable, 'retryable', false)));

    body = jsonEncode({'detail': [{'loc': ['body', 'name'], 'msg': 'too short'}]});
    await expectLater(api.me(), throwsA(isA<ApiException>()
        .having((e) => e.message, 'message', 'Some fields are not valid.')));

    status = 503;
    body = 'oops';
    await expectLater(api.me(), throwsA(isA<ApiException>().having((e) => e.isRetryable, 'retryable', true)));
  });

  test('an unreachable server is a network error the queue retries later', () async {
    final api = ApiClient(baseUrl: 'http://api', auth: auth,
        client: MockClient((_) async => throw const SocketException('no route')));
    await expectLater(api.me(), throwsA(isA<ApiException>()
        .having((e) => e.isNetwork, 'network', true)
        .having((e) => e.isRetryable, 'retryable', true)));
  });

  test('scan upload sends scan_id, capture time, crop and the photo', () async {
    late http.Request seen;
    final api = ApiClient(baseUrl: 'http://api', auth: auth, client: MockClient((req) async {
      seen = req;
      return http.Response(fixtureText('diagnosis_confirmed'), 201);
    }));
    final d = await api.uploadScan(scanId: 'abc12345', farmId: 'f1', cropType: 'tomato',
        capturedAt: DateTime.utc(2026, 11, 20, 8), jpeg: Uint8List.fromList([1, 2, 3]));
    expect(d.label, 'Tomato early blight');
    final body = latin1.decode(seen.bodyBytes);
    expect(seen.headers['Authorization'], startsWith('Bearer dev:'));
    expect(seen.headers['content-type'], startsWith('multipart/form-data'));
    for (final part in ['name="scan_id"', 'abc12345', 'name="crop_type"', 'tomato',
        '2026-11-20T08:00:00.000Z', 'name="image"; filename="abc12345.jpg"']) {
      expect(body, contains(part));
    }
  });

  test('form validators for the login screen', () {
    expect(validateEmail(''), isNotNull);
    expect(validateEmail('not-an-email'), isNotNull);
    expect(validateEmail('aisha@example.com'), isNull);
    expect(validatePassword('short'), isNotNull);
    expect(validatePassword('longenough'), isNull);
  });
}
