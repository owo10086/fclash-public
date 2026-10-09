import 'dart:async';
import 'dart:ui';

extension FutureExt<T> on Future<T> {
  Future<T> withTimeout({
    Duration? timeout,
    String? tag,
    VoidCallback? onLast,
    FutureOr<T> Function()? onTimeout,
  }) async {
    final realTimeout = timeout ?? const Duration(minutes: 3);
    try {
      return await this.timeout(
        realTimeout,
        onTimeout: () {
          if (onTimeout != null) return onTimeout();
          throw TimeoutException('${tag ?? runtimeType} timeout');
        },
      );
    } finally {
      onLast?.call();
    }
  }
}

extension CompleterExt<T> on Completer<T> {
  void safeCompleter(T value) {
    if (isCompleted) {
      return;
    }
    complete(value);
  }
}
