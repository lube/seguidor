from kalman_filter import KalmanFilter


def test_initialization():
    kf = KalmanFilter(1, 1)
    assert kf.process_variance == 1
    assert kf.estimated_measurement_variance == 1
    assert kf.posteri_estimate == 0.0
    assert kf.posteri_error_estimate == 1.0


def test_input_latest_noisy_measurement():
    kf = KalmanFilter(1, 1)
    kf.input_latest_noisy_measurement(5)
    assert kf.posteri_estimate != 0.0
    assert kf.posteri_error_estimate != 1.0


def test_get_latest_estimated_measurement():
    kf = KalmanFilter(1, 1)
    kf.input_latest_noisy_measurement(5)
    assert kf.get_latest_estimated_measurement() == kf.posteri_estimate


def test_zero_process_variance():
    kf = KalmanFilter(0, 1)
    kf.input_latest_noisy_measurement(5)
    assert kf.posteri_estimate != 0.0


def test_zero_measurement_variance():
    kf = KalmanFilter(1, 0)
    kf.input_latest_noisy_measurement(5)
    assert kf.posteri_estimate == 5.0


def test_high_process_variance():
    kf = KalmanFilter(1e6, 1)
    kf.input_latest_noisy_measurement(5)
    assert kf.posteri_estimate < 5


def test_high_measurement_variance():
    kf = KalmanFilter(1, 1e6)
    kf.input_latest_noisy_measurement(5)
    assert kf.posteri_estimate > 0


def test_large_measurement_input():
    kf = KalmanFilter(1, 1)
    kf.input_latest_noisy_measurement(1e6)
    assert kf.posteri_estimate > 0


def test_negative_measurement_input():
    kf = KalmanFilter(1, 1)
    kf.input_latest_noisy_measurement(-5)
    assert kf.posteri_estimate < 0
