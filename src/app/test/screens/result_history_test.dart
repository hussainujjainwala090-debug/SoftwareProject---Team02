// TC-04 to TC-10, TC-15, TC-16: result, history and report screens.
import 'dart:convert';

import 'package:agriscan/screens/history_screen.dart';
import 'package:agriscan/screens/report_screen.dart';
import 'package:agriscan/screens/result_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../helpers.dart';

void main() {
  testWidgets('confirmed result: disease, confidence, severity, spread risk, treatments', (tester) async {
    final app = TestApp();
    await app.show(tester, ResultScreen(diagnosisId: app.backend.confirmedId));
    final d = fixture('diagnosis_confirmed') as Map;
    expect(find.text('Tomato early blight'), findsOneWidget);
    expect(find.text('Confidence: ${((d['confidence'] as num) * 100).round()}%'), findsOneWidget);
    expect(find.text('Severity'), findsOneWidget);
    expect(find.text('Spread risk'), findsOneWidget);
    expect(find.textContaining('Weather: 34 °C, humidity 78%'), findsOneWidget);
    expect(find.text('Original'), findsOneWidget); // overlay switch (FR-07)
    for (final tab in ['Organic', 'Chemical', 'Preventive']) {
      expect(find.text(tab), findsOneWidget);
    }
    // SD-2: opening the result refreshes the spread risk.
    expect(app.backend.sent('GET', '/spread-risk'), hasLength(1));
    // Farmers do not get the agronomist panel.
    expect(find.text('Agronomist review'), findsNothing);
  });

  testWidgets('uncertain result: advice, retake and no severity', (tester) async {
    final app = TestApp();
    await app.show(tester, ResultScreen(diagnosisId: app.backend.uncertainId));
    expect(find.text('Uncertain'), findsOneWidget);
    expect(find.text('Uncertain result'), findsOneWidget);
    expect(find.textContaining('ask an agronomist'), findsOneWidget);
    expect(find.text('Retake photo'), findsOneWidget);
    expect(find.text('Severity'), findsNothing);
    expect(app.backend.sent('GET', '/spread-risk'), isEmpty);
  });

  testWidgets('feedback: "Yes" is sent once and then shown', (tester) async {
    final app = TestApp();
    await app.show(tester, ResultScreen(diagnosisId: app.backend.uncertainId));
    await scrollTo(tester, find.text('Yes'));
    await tester.tap(find.text('Yes'));
    await tester.pumpAndSettle();
    expect(jsonDecode(app.backend.sent('POST', '/feedback').single.body), {'correct': true});
    expect(find.text('You said yes. Thank you!'), findsOneWidget);
  });

  testWidgets('agronomist confirms an uncertain result with the correct disease', (tester) async {
    final app = TestApp(role: 'agronomist');
    await app.show(tester, ResultScreen(diagnosisId: app.backend.uncertainId));
    await scrollTo(tester, find.byKey(const Key('reviewChoice')));
    expect(find.text('Agronomist review'), findsOneWidget);
    expect(find.text('Was this correct?'), findsNothing);
    await tester.tap(find.byKey(const Key('reviewChoice')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tomato leaf mold').last);
    await tester.pumpAndSettle();
    await scrollTo(tester, find.text('Confirm or correct'));
    await tester.tap(find.text('Confirm or correct'));
    await tester.pumpAndSettle();
    final sent = jsonDecode(app.backend.sent('POST', '/review').single.body) as Map;
    final mold = (fixture('diseases') as List).firstWhere((d) => d['name'] == 'Tomato leaf mold');
    expect(sent, {'disease_id': mold['disease_id']});
    expect(find.text('Review saved'), findsOneWidget);
  });

  testWidgets('export creates a PDF report and opens the report screen', (tester) async {
    final app = TestApp();
    await app.show(tester, ResultScreen(diagnosisId: app.backend.confirmedId));
    await scrollTo(tester, find.text('Save and export report'));
    await tester.tap(find.text('Save and export report'));
    await tester.pumpAndSettle();
    expect(app.backend.sent('POST', '/reports'), hasLength(1));
    expect(find.byType(ReportScreen), findsOneWidget);
    expect(find.text('Just created'), findsOneWidget);
    expect(find.byTooltip('Copy share link'), findsOneWidget);
  });

  testWidgets('history lists saved diagnoses and filters them', (tester) async {
    final app = TestApp();
    await app.show(tester, const HistoryScreen());
    expect(find.text('Tomato early blight'), findsOneWidget);
    expect(find.text('Uncertain'), findsWidgets);
    expect(find.textContaining('Needs review'), findsOneWidget);

    await tester.tap(find.descendant(of: find.byType(SegmentedButton<String?>), matching: find.text('Uncertain')));
    await tester.pumpAndSettle();
    expect(app.backend.requests.last.url.queryParameters, {'status': 'uncertain'});

    await tester.enterText(find.byKey(const Key('search')), '2026-11-21');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(app.backend.requests.last.url.queryParameters,
        {'status': 'uncertain', 'date_from': '2026-11-21', 'date_to': '2026-11-21'});

    await tester.enterText(find.byKey(const Key('search')), 'blight');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(app.backend.requests.last.url.queryParameters, {'status': 'uncertain', 'q': 'blight'});
  });
}
