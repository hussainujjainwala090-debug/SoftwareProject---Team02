import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import 'package:sqflite/sqflite.dart';

import 'config.dart';
import 'screens/home_shell.dart';
import 'screens/login_screen.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/scan_queue.dart';
import 'state/session.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const config = AppConfig.fromEnvironment;

  final AuthService auth;
  if (config.useFirebase) {
    await Firebase.initializeApp(); // needs the app's Firebase config files
    auth = FirebaseAuthService();
  } else {
    auth = DevAuthService();
  }
  final api = ApiClient(baseUrl: config.apiBaseUrl, auth: auth);

  // SQLite on the phone; the browser preview keeps the queue in memory only.
  final QueueStore store = kIsWeb
      ? MemoryQueueStore()
      : await SqliteQueueStore.open(p.join(await getDatabasesPath(), 'agriscan_queue.db'));
  final queue = ScanQueue(store, (s) => api.uploadScan(
      scanId: s.scanId, farmId: s.farmId, cropType: s.cropType, capturedAt: s.capturedAt, jpeg: s.image));
  await queue.load();

  final session = Session(api, auth, onReady: config.useFirebase ? _registerForPush : null);
  // Upload queued scans when the connection comes back (FR-12).
  Connectivity().onConnectivityChanged.listen((result) {
    if (session.status == SessionStatus.ready && !result.contains(ConnectivityResult.none)) {
      queue.syncAll();
    }
  });

  runApp(AgriScanApp(session: session, queue: queue));
}

/// Send this phone's FCM token to the backend for climate alerts (FR-11).
Future<void> _registerForPush(ApiClient api) async {
  final messaging = FirebaseMessaging.instance;
  await messaging.requestPermission();
  // The backend sends with messaging.Message(token=...), which needs the FCM
  // registration token. The newer register()/onRegistered API gives an
  // installation ID for a different send method, so the token API is kept.
  // ignore: deprecated_member_use
  final token = await messaging.getToken();
  if (token != null) await api.setFcmToken(token);
  // ignore: deprecated_member_use
  messaging.onTokenRefresh.listen(api.setFcmToken);
}

class AgriScanApp extends StatelessWidget {
  const AgriScanApp({super.key, required this.session, required this.queue});
  final Session session;
  final ScanQueue queue;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: session),
        ChangeNotifierProvider.value(value: queue),
        Provider.value(value: session.api),
      ],
      child: MaterialApp(
        title: 'AgriScan',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
          filledButtonTheme: FilledButtonThemeData(
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
          ),
          outlinedButtonTheme: OutlinedButtonThemeData(
            style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          ),
        ),
        home: Consumer<Session>(
          builder: (context, s, _) =>
              s.status == SessionStatus.ready ? const HomeShell() : const LoginScreen(),
        ),
      ),
    );
  }
}
