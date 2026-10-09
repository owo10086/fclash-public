import 'dart:async';

class VisiblePolling<T> {
  VisiblePolling({
    required Duration interval,
    required Future<T> Function() request,
    required void Function(T) onData,
    required Object? Function() readGeneration,
    void Function(Object, StackTrace)? onError,
  }) : _interval = interval,
       _request = request,
       _onData = onData,
       _readGeneration = readGeneration,
       _onError = onError;

  final Duration _interval;
  final Future<T> Function() _request;
  final void Function(T) _onData;
  final Object? Function() _readGeneration;
  final void Function(Object, StackTrace)? _onError;
  Timer? _timer;
  bool _visible = false;
  bool _disposed = false;
  bool _inFlight = false;
  bool _pending = false;
  int _revision = 0;

  void setVisible(bool visible) {
    if (_disposed || _visible == visible) return;
    _visible = visible;
    _revision++;
    _timer?.cancel();
    _timer = null;
    _pending = visible;
    if (visible) unawaited(_run());
  }

  void refresh() {
    if (_disposed) return;
    _revision++;
    _timer?.cancel();
    _timer = null;
    _pending = _visible;
    if (_visible) unawaited(_run());
  }

  Future<void> _run() async {
    if (_disposed || !_visible || _inFlight) return;
    _inFlight = true;
    _pending = false;
    final revision = _revision;
    try {
      final generation = _readGeneration();
      final value = await _request();
      if (!_disposed &&
          _visible &&
          revision == _revision &&
          generation == _readGeneration()) {
        _onData(value);
      }
    } catch (error, stackTrace) {
      if (!_disposed) _onError?.call(error, stackTrace);
    } finally {
      _inFlight = false;
      if (!_disposed && _visible) {
        // 等旧请求结束后再立即刷新，避免来回切页产生并发请求。
        if (_pending) {
          unawaited(_run());
        } else {
          _timer = Timer(_interval, () => unawaited(_run()));
        }
      }
    }
  }

  void dispose() {
    _disposed = true;
    _revision++;
    _pending = false;
    _timer?.cancel();
    _timer = null;
  }
}
