import 'package:flutter/material.dart';

import '../data/models.dart';
import '../theme/palette.dart';

/// A small colored label for a kind of change, as on the desktop app's cards
class EventBadge extends StatelessWidget {
  final EventKind kind;
  final String text;

  const EventBadge({super.key, required this.kind, required this.text});

  @override
  Widget build(BuildContext context) {
    final color = Palette.of(context).event(kind);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(text, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}
