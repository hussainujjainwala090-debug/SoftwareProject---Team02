import 'package:flutter/foundation.dart';

import '../models.dart';
import '../services/api_client.dart';
import '../services/auth_service.dart';

enum SessionStatus { signedOut, needsRegistration, ready }

/// Who is signed in and their farms (FR-01, FR-02).
class Session extends ChangeNotifier {
  Session(this.api, this.auth, {this.onReady});

  final ApiClient api;
  final AuthService auth;

  /// Called once the user is known, e.g. to register the phone for push alerts.
  final Future<void> Function(ApiClient api)? onReady;

  SessionStatus status = SessionStatus.signedOut;
  AppUser? user;
  List<Farm> farms = [];
  String? selectedFarmId;

  Farm? get selectedFarm {
    for (final f in farms) {
      if (f.farmId == selectedFarmId) return f;
    }
    return farms.isEmpty ? null : farms.first;
  }

  Future<void> signIn(String email, String password) async {
    await auth.signIn(email, password);
    await _loadUser();
  }

  /// Create the sign-in account, then the AgriScan user record.
  Future<void> register(String email, String password, String name, String role) async {
    if (status != SessionStatus.needsRegistration) await auth.createAccount(email, password);
    try {
      await api.register(name, role);
    } on ApiException catch (e) {
      if (e.statusCode != 409) rethrow; // 409: already registered, just load it
    }
    await _loadUser();
  }

  Future<void> _loadUser() async {
    try {
      user = await api.me();
    } on ApiException catch (e) {
      if (e.isNotRegistered) {
        status = SessionStatus.needsRegistration;
        notifyListeners();
        return;
      }
      await auth.signOut();
      rethrow;
    }
    await refreshFarms();
    status = SessionStatus.ready;
    notifyListeners();
    if (onReady != null) {
      try {
        await onReady!(api);
      } on Object catch (e) {
        debugPrint('Push registration failed: $e');
      }
    }
  }

  Future<void> refreshFarms() async {
    farms = user!.isAgronomist ? [] : await api.farms();
    notifyListeners();
  }

  void selectFarm(String farmId) {
    selectedFarmId = farmId;
    notifyListeners();
  }

  Future<Farm> saveFarm({String? farmId, required String name, required double latitude,
      required double longitude, required List<String> crops}) async {
    final farm = farmId == null
        ? await api.createFarm(name, latitude, longitude, crops)
        : await api.updateFarm(farmId, name, latitude, longitude, crops);
    selectedFarmId = farm.farmId;
    await refreshFarms();
    return farm;
  }

  Future<void> signOut() async {
    await auth.signOut();
    status = SessionStatus.signedOut;
    user = null;
    farms = [];
    selectedFarmId = null;
    notifyListeners();
  }
}
