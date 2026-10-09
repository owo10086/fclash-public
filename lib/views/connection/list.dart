import 'package:fl_clash/models/common.dart';
import 'package:flutter/material.dart';
import 'package:super_sliver_list/super_sliver_list.dart';

class TrackerInfoList extends StatelessWidget {
  final List<TrackerInfo> records;
  final Widget Function(BuildContext, TrackerInfo) itemBuilder;
  final ScrollController? controller;
  final ScrollPhysics? physics;
  final bool reverse;
  final bool shrinkWrap;

  const TrackerInfoList({
    super.key,
    required this.records,
    required this.itemBuilder,
    this.controller,
    this.physics,
    this.reverse = false,
    this.shrinkWrap = false,
  });

  @override
  Widget build(BuildContext context) {
    final indices = {
      for (var index = 0; index < records.length; index++)
        records[index].id: index,
    };
    return SuperListView.builder(
      controller: controller,
      reverse: reverse,
      shrinkWrap: shrinkWrap,
      physics: physics,
      padding: EdgeInsets.zero,
      itemCount: records.length,
      findChildIndexCallback: (key) =>
          key is ValueKey<String> ? indices[key.value] : null,
      itemBuilder: (context, index) {
        final record = records[index];
        final hasSeparator = index < records.length - 1;
        return Column(
          key: ValueKey(record.id),
          mainAxisSize: MainAxisSize.min,
          children: [
            if (reverse && hasSeparator) const Divider(height: 0),
            itemBuilder(context, record),
            if (!reverse && hasSeparator) const Divider(height: 0),
          ],
        );
      },
    );
  }
}
