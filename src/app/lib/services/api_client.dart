import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models.dart';
import 'auth_service.dart';

/// Error from the backend. statusCode is null when the server could not be reached.
class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int? statusCode;
  final String message;

  bool get isNetwork => statusCode == null;
  bool get isRetryable => statusCode == null || statusCode! >= 500;
  bool get isUnauthorized => statusCode == 401;
  bool get isNotRegistered => statusCode == 403 && message.contains('not registered');

  @override
  String toString() => message;
}

/// HTTPS/REST client for the FastAPI backend (/api/v1). Every request carries
/// the Firebase ID token (or a development token) as a bearer token.
class ApiClient {
  ApiClient({required this.baseUrl, required this.auth, http.Client? client})
      : _http = client ?? http.Client();

  final String baseUrl;
  final AuthService auth;
  final http.Client _http;

  Uri _uri(String path, [Map<String, String?>? query]) {
    final q = {for (final e in (query ?? {}).entries) if (e.value != null && e.value!.isNotEmpty) e.key: e.value!};
    return Uri.parse('$baseUrl/api/v1$path').replace(queryParameters: q.isEmpty ? null : q);
  }

  Future<Map<String, String>> _headers({bool json = true}) async {
    final token = await auth.idToken();
    return {
      if (token != null) 'Authorization': 'Bearer $token',
      if (json) 'Content-Type': 'application/json',
    };
  }

  Future<dynamic> _send(Future<http.Response> Function() request) async {
    http.Response resp;
    try {
      resp = await request();
    } on Exception {
      throw ApiException(null, 'Cannot reach the server. Check your internet connection.');
    }
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return resp.body.isEmpty ? null : jsonDecode(utf8.decode(resp.bodyBytes));
    }
    String message = 'Server error (${resp.statusCode})';
    try {
      final detail = (jsonDecode(utf8.decode(resp.bodyBytes)) as Map)['detail'];
      message = detail is String ? detail : 'Some fields are not valid.';
    } on Object {
      // keep the generic message
    }
    throw ApiException(resp.statusCode, message);
  }

  Future<dynamic> _get(String path, [Map<String, String?>? query]) async =>
      _send(() async => _http.get(_uri(path, query), headers: await _headers()));

  Future<dynamic> _post(String path, [Object? body]) async => _send(() async =>
      _http.post(_uri(path), headers: await _headers(), body: body == null ? null : jsonEncode(body)));

  Future<dynamic> _put(String path, Object body) async =>
      _send(() async => _http.put(_uri(path), headers: await _headers(), body: jsonEncode(body)));

  // ------------------------------------------------------------ users ----
  Future<AppUser> register(String name, String role) async =>
      AppUser.fromJson(await _post('/users/register', {'name': name, 'role': role}));

  Future<AppUser> me() async => AppUser.fromJson(await _get('/users/me'));

  Future<void> setFcmToken(String token) => _put('/users/me/fcm-token', {'fcm_token': token});

  // ------------------------------------------------------------ farms ----
  Future<List<Farm>> farms() async =>
      [for (final f in await _get('/farms') as List) Farm.fromJson(f as Map<String, dynamic>)];

  Map<String, dynamic> _farmBody(String name, double lat, double lon, List<String> crops) =>
      {'name': name, 'latitude': lat, 'longitude': lon, 'crops': crops};

  Future<Farm> createFarm(String name, double lat, double lon, List<String> crops) async =>
      Farm.fromJson(await _post('/farms', _farmBody(name, lat, lon, crops)));

  Future<Farm> updateFarm(String id, String name, double lat, double lon, List<String> crops) async =>
      Farm.fromJson(await _put('/farms/$id', _farmBody(name, lat, lon, crops)));

  Future<Dashboard> dashboard(String farmId) async =>
      Dashboard.fromJson(await _get('/farms/$farmId/dashboard'));

  // ------------------------------------------------------------ scans ----
  /// Upload one scan (FR-03). scanId and capturedAt come from the offline
  /// queue, so a retry never creates a second diagnosis (FR-12).
  Future<Diagnosis> uploadScan({
    required String scanId,
    required String farmId,
    required String cropType,
    required DateTime capturedAt,
    required Uint8List jpeg,
  }) async {
    return Diagnosis.fromJson(await _send(() async {
      final req = http.MultipartRequest('POST', _uri('/scans'))
        ..headers.addAll(await _headers(json: false))
        ..fields['farm_id'] = farmId
        ..fields['crop_type'] = cropType
        ..fields['scan_id'] = scanId
        ..fields['captured_at'] = capturedAt.toUtc().toIso8601String()
        ..files.add(http.MultipartFile.fromBytes('image', jpeg, filename: '$scanId.jpg'));
      return http.Response.fromStream(await _http.send(req));
    }));
  }

  Future<List<Diagnosis>> history({String? status, String? crop, String? q, String? dateFrom,
      String? dateTo, String? farmId}) async {
    final list = await _get('/diagnoses', {
      'status': status, 'crop': crop, 'q': q, 'date_from': dateFrom, 'date_to': dateTo, 'farm_id': farmId,
    }) as List;
    return [for (final d in list) Diagnosis.fromJson(d as Map<String, dynamic>)];
  }

  Future<Diagnosis> diagnosis(String id) async => Diagnosis.fromJson(await _get('/diagnoses/$id'));

  Future<SpreadRiskInfo> spreadRisk(String id) async =>
      SpreadRiskInfo.fromJson(await _get('/diagnoses/$id/spread-risk'));

  Future<Diagnosis> review(String id, String? diseaseId) async =>
      Diagnosis.fromJson(await _post('/diagnoses/$id/review', {'disease_id': diseaseId}));

  Future<void> feedback(String id, bool correct, [String? comment]) =>
      _post('/diagnoses/$id/feedback', {'correct': correct, 'comment': ?comment});

  Future<Report> createReport(String id) async => Report.fromJson(await _post('/diagnoses/$id/reports'));

  Future<List<Report>> reports(String id) async => [
        for (final r in await _get('/diagnoses/$id/reports') as List) Report.fromJson(r as Map<String, dynamic>)
      ];

  // --------------------------------------------------- knowledge base ----
  Future<List<Disease>> diseases({String? crop, String? q, bool includeArchived = false}) async {
    final list = await _get('/diseases',
        {'crop': crop, 'q': q, 'include_archived': includeArchived ? 'true' : null}) as List;
    return [for (final d in list) Disease.fromJson(d as Map<String, dynamic>)];
  }

  Map<String, dynamic> _diseaseBody(String name, String crop, String? symptoms, List<Treatment> t) =>
      {'name': name, 'crop_type': crop, 'symptoms': symptoms, 'treatments': [for (final x in t) x.toJson()]};

  Future<Disease> createDisease(String name, String crop, String? symptoms, List<Treatment> t) async =>
      Disease.fromJson(await _post('/admin/diseases', _diseaseBody(name, crop, symptoms, t)));

  Future<Disease> updateDisease(String id, String name, String crop, String? symptoms, List<Treatment> t) async =>
      Disease.fromJson(await _put('/admin/diseases/$id', _diseaseBody(name, crop, symptoms, t)));

  Future<Disease> setArchived(String id, bool archived) async =>
      Disease.fromJson(await _post('/admin/diseases/$id/${archived ? 'archive' : 'restore'}'));

  // ------------------------------------------------------------ admin ----
  Future<List<AppUser>> users() async =>
      [for (final u in await _get('/admin/users') as List) AppUser.fromJson(u as Map<String, dynamic>)];

  /// FR-18: the admin creates an account with a first password.
  Future<AppUser> createUser(String name, String email, String password, String role) async =>
      AppUser.fromJson(await _post('/admin/users', {'name': name, 'email': email, 'password': password, 'role': role}));

  Future<AppUser> setDisabled(String userId, bool disabled) async =>
      AppUser.fromJson(await _post('/admin/users/$userId/${disabled ? 'disable' : 'enable'}'));

  Future<AppUser> changeRole(String userId, String role) async => AppUser.fromJson(await _send(
      () async => _http.patch(_uri('/admin/users/$userId/role'), headers: await _headers(),
          body: jsonEncode({'role': role}))));

  Future<void> removeUser(String userId) async =>
      _send(() async => _http.delete(_uri('/admin/users/$userId'), headers: await _headers()));

  Future<ModelAccuracy> modelAccuracy() async => ModelAccuracy.fromJson(await _get('/admin/model-accuracy'));
}
