<!--
Thanks for contributing! Please fill this out so reviews are fast.
Skip sections that don't apply with "n/a".
-->

## Summary

<!-- One or two sentences on what this PR changes and why. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (behaviour or interface change)
- [ ] Documentation only
- [ ] Build / CI / tooling

## Related issues

<!-- e.g. Closes #12, Refs #34 -->

## How has this been tested?

<!--
Hardware tested on, exact reproduction steps, observed topic rates, runtime
of validate.sh, and whether you drove the camera far enough for keyframes
and loop closure. A short terminal paste is ideal.
-->

- Platform:
- ROS 2 distro:
- ZED SDK version:
- Duration of map build:

### Test output

```
$ ./validate.sh
...
```

## Documentation

- [ ] README updated (if launch args, parameters, or workflow changed)
- [ ] `docs/` updated (if architecture changed)
- [ ] `CHANGELOG.md` entry added under `## [Unreleased]`

## Licensing acknowledgement

- [ ] I agree that my contribution is licensed under the GNU AGPL-3.0-only.

## Checklist

- [ ] My code follows the style guidelines in `CONTRIBUTING.md`
- [ ] `colcon build --symlink-install` succeeds without warnings
- [ ] `ros2 launch zed_slam_bringup slam.launch.py` comes up cleanly
- [ ] New/changed parameters have clear inline comments explaining *why*
