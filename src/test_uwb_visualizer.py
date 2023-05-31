import unittest.mock as mock

from uwb_visualizer import UWBVisualizer  # replace with your actual module name


def test_save_and_load_anchor_colors():
    visualizer = UWBVisualizer()

    # Mocking the open function to simulate file operations
    with mock.patch('builtins.open', mock.mock_open(read_data='[0, 1, 2, 3]')) as m:
        # Save anchor colors
        visualizer.anchor_colors = [0, 1, 2, 3]
        visualizer.save_anchor_colors()
        m.assert_called_once_with('./../anchor_colors.json', 'w')

        # Load anchor colors
        visualizer.load_anchor_colors()
        m.assert_called_with('./../anchor_colors.json', 'r')
        assert visualizer.anchor_colors == [0, 1, 2, 3]


def test_save_and_load_ui_configs():
    visualizer = UWBVisualizer()

    with mock.patch('builtins.open', mock.mock_open(read_data='[100, 200, 1.5, 90]')) as m:
        # Save UI configurations
        visualizer.offset_x = 100
        visualizer.offset_y = 200
        visualizer.scale = 1.5
        visualizer.rotation_angle = 90
        visualizer.save_ui_configs()
        m.assert_called_once_with('./../ui.json', 'w')

        # Load UI configurations
        visualizer.load_ui_configs()
        m.assert_called_with('./../ui.json', 'r')
        assert visualizer.offset_x == 100
        assert visualizer.offset_y == 200
        assert visualizer.scale == 1.5
        assert visualizer.rotation_angle == 90


def test_update_position():
    visualizer = UWBVisualizer()
    visualizer.update_position([1.0, 2.0, 3.0])
    assert visualizer.x_filtered == 1.0
    assert visualizer.y_filtered == 2.0
    assert visualizer.z_filtered == 3.0


def test_update_anchor_positions():
    visualizer = UWBVisualizer()
    visualizer.update_anchor_positions([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    assert visualizer.anchor_positions == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert visualizer.anchor_colors == [0, 0]  # Default color index is 0


def test_toggle_anchor_color():
    visualizer = UWBVisualizer()
    visualizer.anchor_colors = [0, 0, 0]
    visualizer.toggle_anchor_color(1)
    assert visualizer.anchor_colors == [0, 1, 0]
    visualizer.toggle_anchor_color(1)
    assert visualizer.anchor_colors == [0, 2, 0]
    visualizer.toggle_anchor_color(1)
    assert visualizer.anchor_colors == [0, 3, 0]
    visualizer.toggle_anchor_color(1)
    assert visualizer.anchor_colors == [0, 0, 0]  # Check wrap around


@mock.patch.object(UWBVisualizer, 'save_anchor_colors')
def test_on_anchor_click(mock_save_anchor_colors):
    visualizer = UWBVisualizer()
    visualizer.anchor_colors = [0, 0, 0]
    mock_event = mock.Mock()  # Create a mock event
    visualizer.on_anchor_click(mock_event, anchor_index=1)
    assert visualizer.anchor_colors == [0, 1, 0]
    mock_save_anchor_colors.assert_called_once()  # Ensure save_anchor_colors is called

