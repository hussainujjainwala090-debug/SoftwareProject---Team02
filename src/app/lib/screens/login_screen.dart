import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../services/auth_service.dart';
import '../state/session.dart';

/// UI-1: Login and registration (FR-01).
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  String _role = 'farmer';
  bool _register = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final session = context.read<Session>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_register || session.status == SessionStatus.needsRegistration) {
        await session.register(_email.text, _password.text, _name.text.trim(), _role);
      } else {
        await session.signIn(_email.text, _password.text);
      }
    } on Object catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _forgotPassword() async {
    if (validateEmail(_email.text) != null) {
      setState(() => _error = 'Enter your email first, then tap "Forgot password?"');
      return;
    }
    try {
      await context.read<Session>().auth.sendPasswordReset(_email.text);
      setState(() => _error = 'A password reset email was sent to ${_email.text.trim()}.');
    } on Object catch (e) {
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final needsRegistration = context.watch<Session>().status == SessionStatus.needsRegistration;
    final register = _register || needsRegistration;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Icon(Icons.eco, size: 56, color: Theme.of(context).colorScheme.primary),
                  Text('AgriScan', textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineLarge),
                  const SizedBox(height: 24),
                  if (needsRegistration)
                    const Text('Finish creating your account.', textAlign: TextAlign.center)
                  else
                    SegmentedButton<bool>(
                      segments: const [
                        ButtonSegment(value: false, label: Text('Log in')),
                        ButtonSegment(value: true, label: Text('Register')),
                      ],
                      selected: {_register},
                      onSelectionChanged: (s) => setState(() => _register = s.first),
                    ),
                  const SizedBox(height: 16),
                  if (register) ...[
                    TextFormField(
                      key: const Key('name'),
                      controller: _name,
                      decoration: const InputDecoration(labelText: 'Full name', border: OutlineInputBorder()),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Enter your name' : null,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      key: const Key('role'),
                      initialValue: _role,
                      decoration: const InputDecoration(labelText: 'I am a', border: OutlineInputBorder()),
                      items: [
                        for (final r in ['farmer', 'farm_owner', 'agronomist'])
                          DropdownMenuItem(value: r, child: Text(roleLabels[r]!)),
                      ],
                      onChanged: (v) => setState(() => _role = v!),
                    ),
                    const SizedBox(height: 12),
                  ],
                  if (!needsRegistration) ...[
                    TextFormField(
                      key: const Key('email'),
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.email],
                      decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
                      validator: validateEmail,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      key: const Key('password'),
                      controller: _password,
                      obscureText: true,
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _busy ? null : _submit(),
                      decoration: const InputDecoration(labelText: 'Password', border: OutlineInputBorder()),
                      validator: register ? validatePassword : (v) => (v ?? '').isEmpty ? 'Enter your password' : null,
                    ),
                  ],
                  const SizedBox(height: 16),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: _busy
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                        : Text(register ? 'Create account' : 'Log in'),
                  ),
                  if (!register) ...[
                    TextButton(onPressed: _forgotPassword, child: const Text('Forgot password?')),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () => setState(() => _register = true),
                      child: const Text('Create account'),
                    ),
                  ],
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
