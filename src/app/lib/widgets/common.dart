import 'package:intl/intl.dart';
import 'package:material_ui/material_ui.dart';

import '../config.dart';

/// App theme: large buttons for farmers with limited technical experience.
/// Full-width buttons are the default; buttons placed in a row set their own size.
ThemeData appTheme() => ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2E7D32)),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
      ),
    );

/// Style for a button that sits in a row next to other widgets.
final ButtonStyle compactButton = OutlinedButton.styleFrom(minimumSize: const Size(72, 44));

String cropName(String crop) => cropLabels[crop] ?? crop;
String formatDate(DateTime d) => DateFormat('d MMM yyyy').format(d.toLocal());
String titleCase(String s) => s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

Color levelColor(BuildContext context, String? level) => switch (level) {
      'high' => Colors.red.shade700,
      'medium' => Colors.orange.shade800,
      'low' => Colors.green.shade700,
      _ => Theme.of(context).colorScheme.outline,
    };

/// Low / medium / high badge for severity and spread risk.
class LevelChip extends StatelessWidget {
  const LevelChip(this.level, {super.key, this.unknown = 'Unavailable'});
  final String? level;
  final String unknown;

  @override
  Widget build(BuildContext context) {
    final color = levelColor(context, level);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color),
      ),
      child: Text(level == null ? unknown : level!.toUpperCase(),
          style: TextStyle(color: color, fontWeight: FontWeight.bold)),
    );
  }
}

/// Card with a title, used for the numbered blocks of the mockups.
class InfoCard extends StatelessWidget {
  const InfoCard({super.key, required this.title, required this.child, this.trailing});
  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
            ?trailing,
          ]),
          const SizedBox(height: 8),
          child,
        ]),
      ),
    );
  }
}

/// Simple full-width message with an icon (errors, empty lists, notices).
class MessageBox extends StatelessWidget {
  const MessageBox(this.text, {super.key, this.icon = Icons.info_outline, this.color, this.onTap});
  final String text;
  final IconData icon;
  final Color? color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.onSurfaceVariant;
    return InkWell(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(color: c.withValues(alpha: 0.6)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(children: [
          Icon(icon, color: c),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: c))),
        ]),
      ),
    );
  }
}

/// Runs an async action, showing its error in a snack bar.
Future<T?> runWithError<T>(BuildContext context, Future<T> Function() action) async {
  try {
    return await action();
  } on Object catch (e) {
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
    return null;
  }
}
