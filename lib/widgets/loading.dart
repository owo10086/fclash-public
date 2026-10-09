import 'package:fl_clash/common/common.dart';
import 'package:flutter/material.dart';

class CommonCircleLoading extends StatelessWidget {
  const CommonCircleLoading({super.key, this.color});

  final Color? color;

  @override
  Widget build(BuildContext context) {
    return CircularProgressIndicator(
      strokeWidth: 2,
      color: color ?? AppColors.secondaryLabel,
    );
  }
}
