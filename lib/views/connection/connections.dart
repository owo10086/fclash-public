import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/common/visible_polling.dart';
import 'package:fl_clash/models/models.dart';
import 'package:fl_clash/providers/visible_polling.dart';
import 'package:fl_clash/widgets/polling_visibility.dart';
import 'package:fl_clash/widgets/widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'item.dart';
import 'list.dart';

class ConnectionsView extends ConsumerStatefulWidget {
  const ConnectionsView({super.key});

  @override
  ConsumerState<ConnectionsView> createState() => _ConnectionsViewState();
}

class _ConnectionsViewState extends ConsumerState<ConnectionsView> {
  final _connectionsStateNotifier = ValueNotifier<TrackerInfosState>(
    const TrackerInfosState(),
  );
  final ScrollController _scrollController = ScrollController();

  late final VisiblePolling<List<TrackerInfo>> _poller;
  late final VoidCallback _unbindGeneration;

  List<Widget> _buildActions() {
    return [
      IconButton(
        onPressed: () async {
          await ref.read(connectionsPollingSourceProvider).closeAll();
          _poller.refresh();
        },
        icon: const Icon(Icons.delete_sweep_outlined),
      ),
    ];
  }

  void _onSearch(String value) {
    _connectionsStateNotifier.value = _connectionsStateNotifier.value.copyWith(
      query: value,
    );
  }

  void _onKeywordsUpdate(List<String> keywords) {
    _connectionsStateNotifier.value = _connectionsStateNotifier.value.copyWith(
      keywords: keywords,
    );
  }

  @override
  void initState() {
    super.initState();
    _poller = VisiblePolling(
      interval: const Duration(seconds: 1),
      request: () => ref.read(connectionsPollingSourceProvider).read(),
      onData: (connections) {
        _connectionsStateNotifier.value = _connectionsStateNotifier.value
            .copyWith(trackerInfos: connections);
      },
      readGeneration: () => readPollingGeneration(ref),
      onError: (error, _) => commonPrint.log('连接刷新失败: $error'),
    );
    _unbindGeneration = bindPollingGeneration(ref, _poller);
  }

  Future<void> _handleBlockConnection(String id) async {
    await ref.read(connectionsPollingSourceProvider).close(id);
    _poller.refresh();
  }

  @override
  void dispose() {
    _poller.dispose();
    _unbindGeneration();
    _connectionsStateNotifier.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PollWhileVisible(
      poller: _poller,
      child: CommonScaffold(
        title: appLocalizations.connections,
        onKeywordsUpdate: _onKeywordsUpdate,
        searchState: AppBarSearchState(onSearch: _onSearch),
        actions: _buildActions(),
        body: ValueListenableBuilder<TrackerInfosState>(
          valueListenable: _connectionsStateNotifier,
          builder: (context, state, _) {
            final connections = state.list;
            if (connections.isEmpty) {
              return NullStatus(
                label: appLocalizations.nullTip(appLocalizations.connections),
                illustration: ConnectionEmptyIllustration(),
              );
            }
            return TrackerInfoList(
              records: connections,
              controller: _scrollController,
              itemBuilder: (context, trackerInfo) => TrackerInfoItem(
                key: Key(trackerInfo.id),
                trackerInfo: trackerInfo,
                onClickKeyword: (value) {
                  context.commonScaffoldState?.addKeyword(value);
                },
                trailing: IconButton(
                  padding: EdgeInsets.zero,
                  visualDensity: VisualDensity.compact,
                  style: IconButton.styleFrom(minimumSize: Size.zero),
                  icon: const Icon(Icons.block),
                  onPressed: () {
                    _handleBlockConnection(trackerInfo.id);
                  },
                ),
                detailTitle: appLocalizations.details(
                  appLocalizations.connection,
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
