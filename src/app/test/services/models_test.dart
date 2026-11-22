// The app's models must parse the backend's real JSON. The fixtures are real
// responses saved by src/backend/scripts/export_fixtures.py.
import 'dart:convert';
import 'dart:io';

import 'package:agriscan/models.dart';
import 'package:flutter_test/flutter_test.dart';

dynamic fixture(String name) => jsonDecode(File('test/fixtures/$name.json').readAsStringSync());

void main() {
  test('confirmed diagnosis from the trained classifier', () {
    final d = Diagnosis.fromJson(fixture('diagnosis_confirmed') as Map<String, dynamic>);
    expect(d.isUncertain, isFalse);
    expect(d.label, 'Tomato early blight');
    expect(d.confidence, inInclusiveRange(0.7, 1.0));
    expect(d.severityLevel, isNotNull);
    expect(d.overlayUrl, startsWith('http'));
    expect(d.treatments.map((t) => t.type).toSet(), {'organic', 'chemical', 'preventive'});
    expect(d.treatments.every((t) => t.safetyWarning.isNotEmpty), isTrue);
    expect(d.weather!.available, isTrue);
  });

  test('uncertain diagnosis has advice and no severity or overlay', () {
    final d = Diagnosis.fromJson(fixture('diagnosis_uncertain') as Map<String, dynamic>);
    expect(d.isUncertain, isTrue);
    expect(d.label, 'Uncertain');
    expect(d.advice, contains('agronomist'));
    expect(d.overlayUrl, isNull);
    expect(d.severityLevel, isNull);
  });

  test('history, farm, user, report, spread risk', () {
    final history = (fixture('history') as List).map((j) => Diagnosis.fromJson(j as Map<String, dynamic>));
    expect(history.length, 2);
    expect(Farm.fromJson(fixture('farm') as Map<String, dynamic>).crops, ['date_palm', 'tomato']);
    expect(AppUser.fromJson(fixture('me') as Map<String, dynamic>).role, 'farmer');
    expect(Report.fromJson(fixture('report') as Map<String, dynamic>).pdfUrl, endsWith('.pdf'));
    expect(SpreadRiskInfo.fromJson(fixture('spread_risk') as Map<String, dynamic>).level, isNotNull);
  });

  test('dashboard, diseases, users and model accuracy', () {
    final dash = Dashboard.fromJson(fixture('dashboard') as Map<String, dynamic>);
    expect(dash.totalScans, 2);
    expect(dash.uncertain, 1);
    expect(dash.scansPerWeek, hasLength(4));
    final diseases = (fixture('diseases') as List).map((j) => Disease.fromJson(j as Map<String, dynamic>));
    expect(diseases.length, 9);
    final users = (fixture('users') as List).map((j) => AppUser.fromJson(j as Map<String, dynamic>));
    expect(users.any((u) => u.isAdmin), isTrue);
    final acc = ModelAccuracy.fromJson(fixture('model_accuracy') as Map<String, dynamic>);
    expect(acc.totalFeedback, 1);
    expect(acc.overallAccuracy, 1.0);
  });
}
