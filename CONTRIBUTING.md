# Contributing to zed_slam_bringup

Thanks for your interest in improving this project! The goal is a clean, reproducible SLAM bringup that works out of the box on NVIDIA Jetson platforms with Stereolabs cameras. Contributions that move us towards that goal are very welcome.

## Ground rules

- **AGPL-3.0-only.** By submitting a pull request, you agree that your contribution is licensed under the GNU AGPL-3.0. You retain copyright to your changes.
- **Play nicely.** Be kind in issues, reviews, and commit messages. Assume the best of other contributors.
- **No unrelated changes.** Keep pull requests focused; open separate PRs for unrelated improvements.

## What makes a good contribution

Roughly in order of "most wanted":

1. **Bug fixes**, especially ones backed by a reproduction recipe.
2. **Platform support** — confirmed working configs for Orin NX, Orin AGX, Xavier, x86 + dGPU.
3. **Documentation** — clearer explanations, corrected typos, screenshots, videos.
4. **New launch presets** — outdoor, GNSS-aided, multi-camera, Nav2 integration.
5. **New tuning profiles** — alternative YAML files under `config/` with clearly-stated tradeoffs.

What to avoid:

- Large refactors with no behaviour change.
- Adding C++/Python nodes — this package is deliberately "config only". If a node is genuinely needed, open an issue first to discuss.
- Vendoring upstream source (ZED wrapper, rtabmap_ros). Keep them as separate repos.

## Development workflow

1. **Fork** the repo and create a feature branch:
   ```bash
   git checkout -b feature/my-change
   ```

2. **Build and test locally** on real hardware where possible:
   ```bash
   cd ~/ros2_ws
   colcon build --symlink-install --packages-select zed_slam_bringup
   source install/setup.bash
   ros2 launch zed_slam_bringup slam.launch.py
   ./src/zed_slam_bringup/validate.sh
   ```

3. **Update docs**. If your change affects launch args, parameters, or runtime behaviour, the `README.md` and/or `docs/` must be updated in the same PR.

4. **Update `CHANGELOG.md`** under `## [Unreleased]`.

5. **Open a PR.** The template will ask you for platform tested, observed topic rates, and a short description.

## Commit message conventions

Follow a light [Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>: <short imperative summary>

<optional longer explanation wrapped at 72 chars>

<optional footer: Refs #123, Closes #456>
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `chore`, `ci`, `test`.

Good:

```
fix: correct RGB topic path for ZED wrapper 5.2.x

The wrapper renamed /zed/zed_node/rgb/image_rect_color to
/zed/zed_node/rgb/color/rect/image in SDK 5.2. Update slam.launch.py
and slam.rviz to match, otherwise rgbd_sync receives no images.

Closes #12
```

Bad:

```
Fixed stuff
```

## Style

- **YAML**: 4-space indent, quote numeric RTAB-Map parameters (`'400'` not `400`) — required by RTAB-Map's parser.
- **Python launch files**: PEP 8, 4-space indent, module docstring at top describing purpose.
- **Shell scripts**: `set -u`, source ROS 2 explicitly, keep portable (no bashisms in `sh` scripts).
- **Markdown**: 80-ish-column wrap preferred but not enforced; tables for structured data.

## Testing

There's no CI on this repo (yet). Before submitting:

- Run `colcon build --symlink-install`. Zero warnings, zero errors.
- Run `ros2 launch zed_slam_bringup slam.launch.py`. All four nodes should come up inside 10 seconds.
- Run `./validate.sh`. Every topic should have a nonzero Hz; every TF chain should resolve.
- If you modified `rtabmap_orinnano.yaml`, drive the camera a few metres and confirm `/rtabmap/info` → `ref_id` increments.

## Reporting bugs

File an issue using the **Bug report** template. Good bug reports include:

- Exact hardware (Jetson model, power mode, camera firmware).
- Software versions: `ros2 --version`, `apt list --installed | grep -E 'rtabmap|zed'`, ZED SDK version.
- Full `ros2 launch` output.
- Output of `./validate.sh`.
- A minimal reproduction: "launch the file, move camera left 50 cm, observe X".

## Security

If you find a security issue (unlikely in a bringup package, but e.g. a credentials leak in a config), please email the maintainer privately rather than opening a public issue.

## Code of Conduct

This project adheres to the [Contributor Covenant](https://www.contributor-covenant.org/) code of conduct. Be excellent to each other.
