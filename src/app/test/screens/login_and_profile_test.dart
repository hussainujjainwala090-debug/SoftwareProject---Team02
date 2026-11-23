// TC-01 (FR-01) login/register screen and TC-02 (FR-02) farm profile screen.
import 'dart:convert';

import 'package:agriscan/screens/farm_profile_screen.dart';
import 'package:agriscan/screens/home_shell.dart';
import 'package:agriscan/screens/login_screen.dart';
import 'package:agriscan/state/session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../helpers.dart';

void main() {
  testWidgets('login checks the fields before sending anything', (tester) async {
    final app = TestApp()..session.status = SessionStatus.signedOut;
    await app.show(tester, const LoginScreen());
    await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
    await tester.pumpAndSettle();
    expect(find.text('Enter your email'), findsOneWidget);
    expect(find.text('Enter your password'), findsOneWidget);
    expect(app.backend.requests, isEmpty);
  });

  testWidgets('register shows name and role; only farmer, farm owner, agronomist', (tester) async {
    final app = TestApp()..session.status = SessionStatus.signedOut;
    await app.show(tester, const LoginScreen());
    await tester.tap(find.text('Register'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('name')), findsOneWidget);
    await tester.tap(find.byKey(const Key('role')));
    await tester.pumpAndSettle();
    expect(find.text('Farm owner'), findsWidgets);
    expect(find.text('Agronomist'), findsWidgets);
    expect(find.text('Admin'), findsNothing);
  });

  testWidgets('register creates the user with the chosen role and signs in', (tester) async {
    final app = TestApp()..session.status = SessionStatus.signedOut;
    await app.show(tester, const LoginScreen());
    await tester.tap(find.text('Register'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('name')), 'Aisha K.');
    await tester.enterText(find.byKey(const Key('email')), 'aisha@example.com');
    await tester.enterText(find.byKey(const Key('password')), 'longpassword');
    await tester.tap(find.widgetWithText(FilledButton, 'Create account'));
    await tester.pumpAndSettle();
    final body = jsonDecode(app.backend.sent('POST', '/users/register').single.body);
    expect(body, {'name': 'Aisha K.', 'role': 'farmer'});
    expect(app.session.status, SessionStatus.ready);
  });

  testWidgets('pressing Enter in the password field logs in', (tester) async {
    final app = TestApp()..session.status = SessionStatus.signedOut;
    await app.show(tester, const LoginScreen());
    await tester.enterText(find.byKey(const Key('email')), 'farmer@example.com');
    await tester.enterText(find.byKey(const Key('password')), 'whatever');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(app.backend.sent('GET', '/users/me'), hasLength(1));
    expect(app.session.status, SessionStatus.ready);
  });

  testWidgets('a signed-in but unregistered account is asked to finish registration', (tester) async {
    final app = TestApp()..session.status = SessionStatus.signedOut;
    app.backend.overrides['GET /users/me'] = (_) => http403();
    await app.show(tester, const LoginScreen());
    await tester.enterText(find.byKey(const Key('email')), 'new@example.com');
    await tester.enterText(find.byKey(const Key('password')), 'whatever');
    await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
    await tester.pumpAndSettle();
    expect(app.session.status, SessionStatus.needsRegistration);
    expect(find.text('Finish creating your account.'), findsOneWidget);
  });

  testWidgets('farm profile validates name, coordinates and crops', (tester) async {
    final app = TestApp(withFarm: false);
    await app.show(tester, const FarmProfileScreen(showMap: false));
    await tester.enterText(find.byKey(const Key('lat')), '95');
    await tester.tap(find.text('Save farm profile'));
    await tester.pumpAndSettle();
    expect(find.text('Farm name is required'), findsOneWidget);
    expect(find.text('Must be between -90 and 90'), findsOneWidget);
    expect(find.text('Tick at least one crop'), findsOneWidget);
    expect(app.backend.sent('POST', '/farms'), isEmpty);
  });

  testWidgets('farm profile saves name, location and ticked crops', (tester) async {
    final app = TestApp(withFarm: false);
    await app.show(tester, const FarmProfileScreen(showMap: false));
    await tester.enterText(find.byKey(const Key('farmName')), 'Al Ain palm farm');
    await tester.enterText(find.byKey(const Key('lat')), '24.2075');
    await tester.enterText(find.byKey(const Key('lon')), '55.7447');
    await tester.tap(find.text('Date palm'));
    await tester.tap(find.text('Tomato'));
    await tester.tap(find.text('Save farm profile'));
    await tester.pumpAndSettle();
    final body = jsonDecode(app.backend.sent('POST', '/farms').single.body);
    expect(body, {'name': 'Al Ain palm farm', 'latitude': 24.2075, 'longitude': 55.7447,
        'crops': ['date_palm', 'tomato']});
    expect(find.text('Farm profile saved'), findsOneWidget);
  });

  testWidgets('farm profile Save button stays above the Android navigation bar', (tester) async {
    // Found on a Galaxy Z Fold7: the app is drawn behind the navigation bar,
    // and the end of this page sat under it.
    final app = TestApp(withFarm: false);
    await app.show(tester, const FarmProfileScreen(showMap: false));
    // Shorter than the phone, because tests leave out the 200 dp map; the page
    // must scroll so its end reaches the bottom edge, as on the phone.
    tester.view.physicalSize = const Size(904, 1400);
    tester.view.devicePixelRatio = 2.625;
    tester.view.padding = const FakeViewPadding(bottom: 126); // 48 dp gesture bar
    addTearDown(tester.view.resetPadding);
    await tester.pumpAndSettle();
    await tester.drag(find.byType(ListView), const Offset(0, -2000)); // to the very end
    await tester.pumpAndSettle();
    final screenHeight = tester.view.physicalSize.height / tester.view.devicePixelRatio;
    expect(tester.getBottomLeft(find.text('Save farm profile')).dy, lessThan(screenHeight - 48));
  });

  testWidgets('tabs depend on the role', (tester) async {
    Future<List<String>> labels(String role) async {
      final app = TestApp(role: role);
      await app.show(tester, const HomeShell());
      return tester.widgetList<NavigationDestination>(find.byType(NavigationDestination))
          .map((d) => d.label).toList();
    }

    expect(await labels('farmer'), ['Scan', 'History', 'Dashboard', 'Profile']);
    expect(await labels('agronomist'), ['History', 'Profile']);
    expect(await labels('admin'), ['Scan', 'History', 'Dashboard', 'Admin', 'Profile']);
  });
}
