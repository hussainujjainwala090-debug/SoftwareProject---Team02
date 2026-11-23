import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import '../config.dart';
import '../services/scan_queue.dart';
import '../state/session.dart';
import '../widgets/common.dart';
import 'admin_screen.dart';
import 'capture_screen.dart';
import 'dashboard_screen.dart';
import 'farm_profile_screen.dart';
import 'history_screen.dart';

/// Bottom navigation: Scan, History, Dashboard and Profile (UI-5, UI-6 item 7).
/// Agronomists do not scan; admins also get the Admin tab (UI-8).
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _Tab {
  const _Tab(this.label, this.icon, this.build);
  final String label;
  final IconData icon;
  final Widget Function() build;
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    // Send anything left in the offline queue from an earlier session.
    WidgetsBinding.instance.addPostFrameCallback((_) => context.read<ScanQueue>().syncAll());
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<Session>().user!;
    final tabs = <_Tab>[
      if (user.canScan) _Tab('Scan', Icons.camera_alt_outlined, () => const CaptureScreen()),
      _Tab('History', Icons.history, () => const HistoryScreen()),
      if (!user.isAgronomist) _Tab('Dashboard', Icons.bar_chart, () => const DashboardScreen()),
      if (user.isAdmin) _Tab('Admin', Icons.admin_panel_settings_outlined, () => const AdminScreen()),
      _Tab('Profile', Icons.person_outline, () => const ProfileScreen()),
    ];
    final index = _index.clamp(0, tabs.length - 1);
    return Scaffold(
      body: SafeArea(child: tabs[index].build()),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [for (final t in tabs) NavigationDestination(icon: Icon(t.icon), label: t.label)],
      ),
    );
  }
}

/// Account details, farm profiles and sign-out.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = context.watch<Session>();
    final user = session.user!;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        ListTile(
          leading: const CircleAvatar(child: Icon(Icons.person)),
          title: Text(user.name),
          subtitle: Text('${user.email}\n${roleLabels[user.role]}'),
          isThreeLine: true,
        ),
        if (!user.isAgronomist) ...[
          const Divider(),
          Text('Farms', style: Theme.of(context).textTheme.titleMedium),
          for (final farm in session.farms)
            ListTile(
              leading: const Icon(Icons.agriculture),
              title: Text(farm.name),
              subtitle: Text(farm.crops.map(cropName).join(', ')),
              trailing: const Icon(Icons.edit_outlined),
              onTap: () => Navigator.of(context)
                  .push(MaterialPageRoute(builder: (_) => FarmProfileScreen(farm: farm))),
            ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.add),
            label: const Text('Add farm'),
            onPressed: () =>
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => const FarmProfileScreen())),
          ),
        ],
        const SizedBox(height: 24),
        TextButton.icon(
          icon: const Icon(Icons.logout),
          label: const Text('Sign out'),
          onPressed: session.signOut,
        ),
      ]),
    );
  }
}
