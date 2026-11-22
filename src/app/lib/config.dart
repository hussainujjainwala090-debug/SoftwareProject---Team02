/// Build-time settings, passed with --dart-define:
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=AUTH_MODE=dev
class AppConfig {
  const AppConfig({required this.apiBaseUrl, required this.authMode});

  /// FastAPI backend address. On the Android emulator, the PC is 10.0.2.2.
  final String apiBaseUrl;

  /// "dev": development tokens for the backend's memory mode (no Firebase).
  /// "firebase": Firebase Authentication and Cloud Messaging.
  final String authMode;

  bool get useFirebase => authMode == 'firebase';

  static const fromEnvironment = AppConfig(
    apiBaseUrl: String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000'),
    authMode: String.fromEnvironment('AUTH_MODE', defaultValue: 'dev'),
  );
}

/// Crops from UI-2 (FR-02); keys match the backend's Crop enum.
const cropLabels = <String, String>{
  'date_palm': 'Date palm',
  'tomato': 'Tomato',
  'cucumber': 'Cucumber',
  'pepper': 'Pepper',
  'other': 'Other',
};

const roleLabels = <String, String>{
  'farmer': 'Farmer',
  'farm_owner': 'Farm owner',
  'agronomist': 'Agronomist',
  'admin': 'Admin',
};
