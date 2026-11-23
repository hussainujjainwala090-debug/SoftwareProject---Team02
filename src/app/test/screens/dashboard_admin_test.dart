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
    expect(find.textContaining('Wk '), findsNWidgets(8)); // scans chart + severity chart
    // FR-13 severity trend: weeks without confirmed diagnoses show "-".
    final trend = find.byKey(const Key('severityTrend'));
    expect(find.text('Severity trend (average affected leaf area)'), findsOneWidget);
    final weeks = d['scans_per_week'] as List;
    for (final w in weeks) {
      final pct = w['avg_affected_area_pct'] as num?;
      final text = pct == null ? '-' : '${pct.toStringAsFixed(1)}%';
      expect(find.descendant(of: trend, matching: find.text(text)), findsWidgets);
    }
    expect(find.descendant(of: trend, matching: find.text('-')),
        findsNWidgets(weeks.where((w) => w['avg_affected_area_pct'] == null).length));
    expect(find.text('Tomato early blight'), findsOneWidget);
    expect(find.textContaining('Climate alert:'), findsOneWidget);
    expect(find.textContaining('Next 24 h:'), findsOneWidget); // FR-14 forecast
  });

  testWidgets('dashboard charts fit a narrow phone with a large font size', (tester) async {
    // Found on a Galaxy Z Fold7: "bottom overflowed by 2.0 pixels" in the
    // tallest chart column. Any overflow makes this test fail.
    final app = TestApp();
    tester.platformDispatcher.textScaleFactorTestValue = 1.3;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await app.show(tester, const DashboardScreen());
    tester.view.physicalSize = const Size(904, 2316);
    tester.view.devicePixelRatio = 2.625;
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('severityTrend')), findsOneWidget);
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

  Future<void> openAddAccount(WidgetTester tester, TestApp app) async {
    await app.show(tester, const AdminScreen());
    await tester.tap(find.text('Users'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Add account'));
    await tester.pumpAndSettle();
  }

  testWidgets('admin creates an account after the form is validated (FR-18)', (tester) async {
    final app = TestApp(role: 'admin');
    Map<String, dynamic>? sent;
    app.backend.overrides['POST /admin/users'] = (req) {
      sent = jsonDecode(req.body) as Map<String, dynamic>;
      return httpJson((fixture('users') as List).first, 201);
    };
    await openAddAccount(tester, app);

    await tester.enterText(find.byKey(const Key('newEmail')), 'not-an-email');
    await tester.enterText(find.byKey(const Key('newPassword')), 'short');
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();
    expect(find.text('Required'), findsOneWidget);
    expect(find.text('Enter a valid email'), findsOneWidget);
    expect(find.text('At least 8 characters'), findsOneWidget);
    expect(sent, isNull);

    final listLoads = app.backend.sent('GET', '/admin/users').length;
    await tester.enterText(find.byKey(const Key('newName')), 'Sara Ali');
    await tester.enterText(find.byKey(const Key('newEmail')), 'sara@example.com');
    await tester.enterText(find.byKey(const Key('newPassword')), 'first-pass-123');
    await tester.tap(find.byKey(const Key('newRole')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Agronomist').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();
    expect(sent, {'name': 'Sara Ali', 'email': 'sara@example.com', 'password': 'first-pass-123', 'role': 'agronomist'});
    expect(find.byType(CreateAccountForm), findsNothing); // dialog closed
    expect(app.backend.sent('GET', '/admin/users').length, listLoads + 1); // list reloaded
  });

  testWidgets('create account shows the backend error, e.g. duplicate email (FR-18)', (tester) async {
    final app = TestApp(role: 'admin');
    app.backend.overrides['POST /admin/users'] =
        (req) => httpJson({'detail': 'A user with this email already exists'}, 409);
    await openAddAccount(tester, app);
    await tester.enterText(find.byKey(const Key('newName')), 'Sara Ali');
    await tester.enterText(find.byKey(const Key('newEmail')), 'sara@example.com');
    await tester.enterText(find.byKey(const Key('newPassword')), 'first-pass-123');
    await tester.tap(find.text('Create'));
    await tester.pumpAndSettle();
    expect(find.text('A user with this email already exists'), findsOneWidget);
    expect(find.byType(CreateAccountForm), findsOneWidget); // stays open to fix
  });
}
