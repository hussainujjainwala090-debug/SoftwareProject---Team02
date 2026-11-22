// TC-13 (FR-13, FR-11 alert card), TC-17 (FR-17) and TC-18 (FR-18): dashboard and admin screens.
import 'dart:convert';

import 'package:agriscan/screens/admin_screen.dart';
import 'package:agriscan/screens/dashboard_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../helpers.dart';

void main() {
  testWidgets('dashboard shows totals, weekly scans, common diseases and climate alert', (tester) async {
    final app = TestApp();
    await app.show(tester, const DashboardScreen());
    final d = fixture('dashboard') as Map;
    expect(find.text('Scans'), findsOneWidget);
    expect(find.text('${d['total_scans']}'), findsWidgets);
    expect(find.text('Scans per week'), findsOneWidget);
    expect(find.textContaining('Wk '), findsNWidgets(4));
    expect(find.text('Tomato early blight'), findsOneWidget);
    expect(find.textContaining('Climate alert:'), findsOneWidget);
  });

  testWidgets('admin knowledge base lists entries with Edit and Archive', (tester) async {
    final app = TestApp(role: 'admin');
    await app.show(tester, const AdminScreen());
    expect(find.text('Tomato early blight'), findsOneWidget);
    expect(find.text('Archive'), findsWidgets);
    expect(find.text('Delete'), findsNothing); // FR-17: archive, never delete
    expect(app.backend.sent('GET', '/diseases').single.url.queryParameters, {'include_archived': 'true'});
  });

  testWidgets('add disease is validated before saving, then sent with treatments', (tester) async {
    final app = TestApp(role: 'admin');
    app.backend.overrides['POST /admin/diseases'] =
        (req) => throw StateError('checked below'); // replaced before saving
    await app.show(tester, const AdminScreen());
    await tester.tap(find.text('Add disease'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add treatment'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(find.text('Required'), findsNWidgets(3)); // name, guidance, safety warning
    expect(app.backend.sent('POST', '/admin/diseases'), isEmpty);

    Map<String, dynamic>? sent;
    app.backend.overrides['POST /admin/diseases'] = (req) {
      sent = jsonDecode(req.body) as Map<String, dynamic>;
      return httpJson(fixture('diseases')[0], 201);
    };
    await tester.enterText(find.byKey(const Key('diseaseName')), 'Cucumber powdery mildew');
    await tester.enterText(find.widgetWithText(TextFormField, 'Guidance'), 'Milk spray weekly');
    await tester.enterText(find.widgetWithText(TextFormField, 'Safety warning'), 'Test on one leaf first');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(sent!['name'], 'Cucumber powdery mildew');
    expect(sent!['treatments'], [
      {'type': 'organic', 'guidance': 'Milk spray weekly', 'safety_warning': 'Test on one leaf first'},
    ]);
  });

  testWidgets('users tab lists accounts with role and status; reports tab shows accuracy', (tester) async {
    final app = TestApp(role: 'admin');
    await app.show(tester, const AdminScreen());
    await tester.tap(find.text('Users'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Farmer · Active'), findsOneWidget);
    await tester.tap(find.byType(PopupMenuButton<String>).first);
    await tester.pumpAndSettle();
    expect(find.text('Change role'), findsOneWidget);
    expect(find.text('Disable'), findsOneWidget);
    expect(find.text('Remove'), findsOneWidget);
    await tester.tapAt(Offset.zero);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Reports'));
    await tester.pumpAndSettle();
    expect(find.textContaining('100.0% correct (1 answers)'), findsOneWidget);
  });
}
