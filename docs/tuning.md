# Tuning guide

The shipped `zed2i_orinnano.yaml` and `rtabmap_orinnano.yaml` are a reasonable default for a Jetson Orin Nano running indoors. This document explains *why* each knob is where it is and how to turn it for different scenarios.

## Decision tree

```
What do you want?
├── Higher camera frame rate (Hz)    -> lower resolution or depth mode
├── Cleaner depth                    -> raise depth_confidence, switch NEURAL
├── Denser map                       -> lower cloud_voxel_size, more keyframes
├── Faster mapping (less drift)      -> lower RGBD/LinearUpdate + AngularUpdate
├── Longer range (outdoor)           -> raise max_depth and Grid/RangeMax
├── More aggressive loop closure     -> raise Kp/MaxFeatures, lower Rtabmap/LoopThr
├── Less memory usage                -> lower Mem/STMSize, raise Rtabmap/TimeThr
└── Survive thermal throttling       -> drop to HD resolution + PERFORMANCE depth
```

## ZED wrapper (`config/zed2i_orinnano.yaml`)

### Raising frame rate

If your scene doesn't need pristine depth:

| Change | Effect |
|---|---|
| `depth.depth_mode: PERFORMANCE` | ~2 Hz faster, slightly noisier depth |
| `general.grab_resolution: VGA` | Large FPS boost, loses detail for SLAM |
| `general.pub_frame_rate: 30.0` | Publish everything at grab rate (doubles CPU on downstream nodes) |
| `depth.point_cloud_freq: 5.0` | Reduce independently-published point-cloud load |

### Outdoor use

| Change | Effect |
|---|---|
| `depth.max_depth: 20.0` | Longer-range depth (quality degrades past 10 m) |
| `depth.min_depth: 0.5` | Avoid near-field artefacts from dust/glare |
| `video.auto_exposure_gain: true` | Essential for sunlight |
| `pos_tracking.set_gravity_as_origin: true` | Already on; keeps z stable outdoors |

### Indoor low-light

| Change | Effect |
|---|---|
| `depth.depth_mode: NEURAL` | Heavier but more robust to low texture (vs `NEURAL_LIGHT`) |
| `video.analog_gain: 10000` | Slightly brighter images |
| `video.denoising: 70` | More noise suppression |

### Disabling IMU fusion

Only do this if your robot is stationary most of the time, or if IMU data is unreliable:

```yaml
pos_tracking:
  imu_fusion: false
```

Expect tracking to degrade under rotation.

## RTAB-Map (`config/rtabmap_orinnano.yaml`)

### Denser keyframes / denser map

```yaml
RGBD/LinearUpdate: '0.02'   # keyframe every 2 cm instead of 5
RGBD/AngularUpdate: '0.02'  # keyframe every ~1° instead of 3°
cloud_voxel_size: 0.02      # 2 cm voxels in published cloud
```

Cost: DB grows ~3x faster, CPU load rises, RViz may slow.

### Sparser keyframes (long-range mapping)

```yaml
RGBD/LinearUpdate: '0.2'
RGBD/AngularUpdate: '0.15'
cloud_voxel_size: 0.1
```

Good for large indoor spaces where 5 cm resolution is overkill.

### More aggressive loop closure

```yaml
Kp/MaxFeatures: '600'        # more features to match against
Vis/MaxFeatures: '800'
Rtabmap/LoopThr: '0.09'      # lower = trigger loop closures more readily
Vis/MinInliers: '12'         # accept matches with fewer inliers
```

Cost: more false positives, which RTAB-Map has to reject; CPU load rises.

### Less memory

On long runs the working memory can grow. To cap it:

```yaml
Mem/STMSize: '20'                    # smaller short-term memory
Rtabmap/TimeThr: '500'               # target max processing time per cycle (ms)
Rtabmap/MemoryThr: '0'               # 0 = unlimited; set >0 for hard node cap
```

### Disabling the 2D grid

If you only care about the 3D cloud:

```yaml
RGBD/CreateOccupancyGrid: 'false'
```

Saves ~5 % CPU on every keyframe.

### Different odometry source

If you're using wheel odometry or a different VIO (e.g. Kimera), remap in the launch file:

```python
('odom', '/my_robot/wheel_odometry'),
```

Consider disabling `RGBD/NeighborLinkRefining` so RTAB-Map trusts the external odometry.

### Localization-only mode

For a saved DB you just want to re-localise inside:

```yaml
Mem/IncrementalMemory: 'false'     # don't add new nodes
Mem/InitWMWithAllNodes: 'true'     # load entire map into working memory
```

Or use the shipped `rtabmap_launch/rtabmap.launch.py` with `localization:=true`.

## Profiling

The fastest way to see where time is going:

```bash
ros2 topic echo /rtabmap/info --once | grep -E "^\s*(proc_time|loop_closure|ref_id|update_time|memory_usage)"
```

Fields of interest:

- `update_time` — total time to process the last frame. Should be < 1 / frame_rate.
- `proc_time` — breakdown by stage (feature extraction, loop closure, optimisation, …).
- `memory_usage` — RAM footprint.

If `update_time` climbs above the frame period, frames are being dropped — either reduce `Kp/MaxFeatures`, bump `Rtabmap/TimeThr`, or accept a lower effective rate.

## When to stop tuning

The shipped defaults give a decent indoor map with no config changes. Tune only when you have a concrete measurement showing something is bottlenecked. "Feels sluggish" is not a measurement — run `validate.sh`, check `/rtabmap/info`, and act on numbers.
