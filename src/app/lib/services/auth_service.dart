import 'package:firebase_auth/firebase_auth.dart' as fb;

/// Sign-in behind one interface (FR-01): Firebase Authentication in production,
/// development tokens for the backend's memory mode.
abstract class AuthService {
  String? get email;
  Future<void> signIn(String email, String password);
  Future<void> createAccount(String email, String password);
  Future<void> sendPasswordReset(String email);
  Future<void> signOut();

  /// Bearer token for the backend, or null when signed out.
  Future<String?> idToken({bool forceRefresh = false});
}

class AuthException implements Exception {
  AuthException(this.message);
  final String message;
  @override
  String toString() => message;
}

final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

String? validateEmail(String? value) {
  if (value == null || value.trim().isEmpty) return 'Enter your email';
  if (!_emailPattern.hasMatch(value.trim())) return 'Enter a valid email address';
  return null;
}

String? validatePassword(String? value) {
  if (value == null || value.length < 8) return 'Use at least 8 characters';
  return null;
}

/// Development sign-in: the backend (memory mode only) accepts
/// `dev:<uid>:<email>`. The password is not checked.
class DevAuthService implements AuthService {
  String? _email;

  @override
  String? get email => _email;

  static String uidFor(String email) =>
      'dev-${email.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '_')}';

  @override
  Future<void> signIn(String email, String password) async => _email = email.trim().toLowerCase();

  @override
  Future<void> createAccount(String email, String password) => signIn(email, password);

  @override
  Future<void> sendPasswordReset(String email) async {
    throw AuthException('Password reset needs Firebase (AUTH_MODE=firebase).');
  }

  @override
  Future<void> signOut() async => _email = null;

  @override
  Future<String?> idToken({bool forceRefresh = false}) async =>
      _email == null ? null : 'dev:${uidFor(_email!)}:$_email';
}

class FirebaseAuthService implements AuthService {
  FirebaseAuthService([fb.FirebaseAuth? auth]) : _auth = auth ?? fb.FirebaseAuth.instance;
  final fb.FirebaseAuth _auth;

  @override
  String? get email => _auth.currentUser?.email;

  Future<void> _wrap(Future<void> Function() action) async {
    try {
      await action();
    } on fb.FirebaseAuthException catch (e) {
      throw AuthException(switch (e.code) {
        'invalid-credential' || 'wrong-password' || 'user-not-found' => 'Wrong email or password',
        'email-already-in-use' => 'An account with this email already exists',
        'weak-password' => 'The password is too weak',
        'user-disabled' => 'This account is disabled',
        'network-request-failed' => 'No internet connection',
        _ => e.message ?? 'Sign-in failed',
      });
    }
  }

  @override
  Future<void> signIn(String email, String password) =>
      _wrap(() => _auth.signInWithEmailAndPassword(email: email.trim(), password: password));

  @override
  Future<void> createAccount(String email, String password) async {
    await _wrap(() => _auth.createUserWithEmailAndPassword(email: email.trim(), password: password));
    await _auth.currentUser?.sendEmailVerification();
  }

  @override
  Future<void> sendPasswordReset(String email) =>
      _wrap(() => _auth.sendPasswordResetEmail(email: email.trim()));

  @override
  Future<void> signOut() => _auth.signOut();

  @override
  Future<String?> idToken({bool forceRefresh = false}) async =>
      _auth.currentUser?.getIdToken(forceRefresh);
}
