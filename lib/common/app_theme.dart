import 'package:fl_clash/enum/enum.dart';
import 'package:flutter/material.dart';

AppearanceMode nextAppearanceModeForBrightness(Brightness brightness) {
  return brightness == Brightness.dark
      ? AppearanceMode.light
      : AppearanceMode.dark;
}

IconData appearanceToggleIconForBrightness(Brightness brightness) {
  return brightness == Brightness.dark
      ? Icons.light_mode_rounded
      : Icons.dark_mode_rounded;
}

String appearanceToggleTooltipForBrightness(Brightness brightness) {
  return brightness == Brightness.dark ? '切换至浅色主题' : '切换至深色主题';
}

@immutable
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  final Color canvas;
  final Color surface;
  final Color surfaceElevated;
  final Color primaryText;
  final Color secondaryText;
  final Color tertiaryText;
  final Color divider;
  final Color accent;
  final Color success;
  final Color warning;
  final Color danger;

  const AppSemanticColors({
    required this.canvas,
    required this.surface,
    required this.surfaceElevated,
    required this.primaryText,
    required this.secondaryText,
    required this.tertiaryText,
    required this.divider,
    required this.accent,
    required this.success,
    required this.warning,
    required this.danger,
  });

  @override
  AppSemanticColors copyWith({
    Color? canvas,
    Color? surface,
    Color? surfaceElevated,
    Color? primaryText,
    Color? secondaryText,
    Color? tertiaryText,
    Color? divider,
    Color? accent,
    Color? success,
    Color? warning,
    Color? danger,
  }) {
    return AppSemanticColors(
      canvas: canvas ?? this.canvas,
      surface: surface ?? this.surface,
      surfaceElevated: surfaceElevated ?? this.surfaceElevated,
      primaryText: primaryText ?? this.primaryText,
      secondaryText: secondaryText ?? this.secondaryText,
      tertiaryText: tertiaryText ?? this.tertiaryText,
      divider: divider ?? this.divider,
      accent: accent ?? this.accent,
      success: success ?? this.success,
      warning: warning ?? this.warning,
      danger: danger ?? this.danger,
    );
  }

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) {
      return this;
    }
    return AppSemanticColors(
      canvas: Color.lerp(canvas, other.canvas, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceElevated: Color.lerp(surfaceElevated, other.surfaceElevated, t)!,
      primaryText: Color.lerp(primaryText, other.primaryText, t)!,
      secondaryText: Color.lerp(secondaryText, other.secondaryText, t)!,
      tertiaryText: Color.lerp(tertiaryText, other.tertiaryText, t)!,
      divider: Color.lerp(divider, other.divider, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
    );
  }
}

abstract class AppThemePalette {
  static const light = AppSemanticColors(
    canvas: Color(0xFFF2F2F7),
    surface: Color(0xFFFFFFFF),
    surfaceElevated: Color(0xFFFFFFFF),
    primaryText: Color(0xFF000000),
    secondaryText: Color(0x993C3C43),
    tertiaryText: Color(0x4D3C3C43),
    divider: Color(0x2E3C3C43),
    accent: Color(0xFF007AFF),
    success: Color(0xFF34C759),
    warning: Color(0xFFFF9500),
    danger: Color(0xFFFF3B30),
  );

  static const dark = AppSemanticColors(
    canvas: Color(0xFF000000),
    surface: Color(0xFF121212),
    surfaceElevated: Color(0xFF1C1C1E),
    primaryText: Color(0xFFF5F5F7),
    secondaryText: Color(0xFFAEAEB2),
    tertiaryText: Color(0xFF8E8E93),
    divider: Color(0xFF38383A),
    accent: Color(0xFF0A84FF),
    success: Color(0xFF30D158),
    warning: Color(0xFFFF9F0A),
    danger: Color(0xFFFF453A),
  );
}

abstract class AppColors {
  static AppSemanticColors _current = AppThemePalette.light;

  static void update(AppSemanticColors colors) {
    _current = colors;
  }

  static Color get systemBackground => _current.surface;
  static Color get secondarySystemBackground => _current.canvas;
  static Color get label => _current.primaryText;
  static Color get secondaryLabel => _current.secondaryText;
  static Color get tertiaryLabel => _current.tertiaryText;
  static Color get separator => _current.divider;
  static Color get systemBlue => _current.accent;
  static Color get systemRed => _current.danger;
  static Color get systemGreen => _current.success;
  static Color get systemOrange => _current.warning;
}

abstract class AppRadius {
  static const double card = 10.0;
  static const double summaryCard = 12.0;
  static const double input = 10.0;
  static const double sheet = 16.0;
  static const double dialog = 12.0;
  static const double buttonPrimary = 10.0;
  static const double buttonSecondary = 10.0;
  static const double chip = 8.0;
  static const double tag = 10.0;
  static const double iconBadge = 8.0;
  static const double navIndicator = 10.0;
  static const double quickCard = summaryCard;
  static const double navItem = 10.0;
  static const double navItemCompact = navItem;
  static const double overlay = 16.0;
}

abstract class AppSpacing {
  static const double pageHorizontal = 16.0;
  static const double pageVertical = 16.0;
  static const double section = 20.0;
  static const double component = 12.0;
  static const double cardPadding = 12.0;
  static const double summaryCardPadding = 16.0;
  static const double cardVertical = 12.0;
  static const double listItemMin = 44.0;
  static const double listItemWithSubtitleMin = 56.0;
  static const double listItemDetailMin = 72.0;
  static const double inputHeight = 40.0;
  static const double buttonHeight = 40.0;
  static const double secondaryButtonHeight = 36.0;
  static const double iconButtonSize = 36.0;
  static const double separatorInset = 16.0;
  static const double sidebarWidth = 184.0;
  static const double sidebarItemHeight = 40.0;
  static const double sidebarItemGap = 8.0;
}

abstract class AppTextStyles {
  static const largeTitleStyle = TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.w700,
    height: 1.25,
  );
  static const title1Style = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w700,
    height: 1.3,
  );
  static const title2Style = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w700,
    height: 1.25,
  );
  static const keyMetricStyle = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w700,
    height: 1.2,
  );
  static const title3Style = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.35,
  );
  static const headlineStyle = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
    height: 1.35,
  );
  static const bodyStyle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.45,
  );
  static const calloutStyle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.45,
  );
  static const subheadlineStyle = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.45,
  );
  static const footnoteStyle = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 1.35,
  );
  static const caption1Style = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    height: 1.35,
  );
  static const caption2Style = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w400,
    height: 1.4,
  );
}
