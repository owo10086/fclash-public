import 'dart:async';

import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/enum/enum.dart';

class Debouncer {
  final Map<Object, Timer?> _operations = {};

  void call(
    Object tag,
    Function func, {
    List<dynamic>? args,
    Duration? duration,
  }) {
    final timer = _operations[tag];
    if (timer != null) {
      timer.cancel();
    }
    _operations[tag] = Timer(duration ?? const Duration(milliseconds: 600), () {
      _operations[tag]?.cancel();
      _operations.remove(tag);
      _runOperation(tag, func, args);
    });
  }

  void cancel(dynamic tag) {
    _operations[tag]?.cancel();
    _operations.remove(tag);
  }
}

class Throttler {
  final Map<Object, Timer?> _operations = {};

  bool call(
    Object tag,
    Function func, {
    List<dynamic>? args,
    Duration duration = const Duration(milliseconds: 600),
    bool fire = false,
  }) {
    final timer = _operations[tag];
    if (timer != null) {
      return true;
    }
    if (fire) {
      _runOperation(tag, func, args);
      _operations[tag] = Timer(duration, () {
        _operations[tag]?.cancel();
        _operations.remove(tag);
      });
    } else {
      _operations[tag] = Timer(duration, () {
        _operations[tag]?.cancel();
        _operations.remove(tag);
        _runOperation(tag, func, args);
      });
    }
    return false;
  }

  void cancel(dynamic tag) {
    _operations[tag]?.cancel();
    _operations.remove(tag);
  }
}

Future<void> _runOperation(Object tag, Function func, List<dynamic>? args) async {
  try {
    await Function.apply(func, args);
  } catch (error, stack) {
    commonPrint.log('操作 $tag 失败：$error\n$stack', logLevel: LogLevel.error);
  }
}

Future<T> retry<T>({
  required Future<T> Function() task,
  int maxAttempts = 3,
  required bool Function(T res) retryIf,
  Duration delay = midDuration,
}) async {
  if (maxAttempts <= 0) {
    throw ArgumentError.value(maxAttempts, 'maxAttempts');
  }
  for (var attempts = 1; attempts <= maxAttempts; attempts++) {
    final res = await task();
    if (!retryIf(res) || attempts == maxAttempts) {
      return res;
    }
    if (delay > Duration.zero) {
      await Future.delayed(delay);
    }
  }
  throw StateError('unreachable');
}

final debouncer = Debouncer();

final throttler = Throttler();
