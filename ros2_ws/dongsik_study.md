# AMR 단순 주행 테스트 정리

현재까지 구성한 것은 **새 맵 생성 → Station waypoint 지정 → Nav2를 이용한 Station 간 단순 이동**이다.

전체 구조는 다음과 같다.

```text
Map 생성
   ↓
demo_map.pgm / demo_map.yaml
   ↓
Waypoint 설정
   ↓
demo_waypoint.yaml
   ↓
AMCL + Nav2 실행
   ↓
robocup_navigator_nav2
   ↓
Station ID 명령
   ↓
AMR 이동
```

---

# 1. 맵 생성 + Waypoint 저장

## 1-1. ROS2 Workspace 준비

새 터미널을 열 때 기본적으로 다음부터 시작한다.

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash
```

---

## 1-2. Cartographer Mapping 실행

```bash
ros2 launch all_in_one_package generate_map_launch.py
```

이 launch를 실행하면 대략 다음 노드들이 함께 실행된다.

```text
serial_test
   ├─ Motor
   ├─ Encoder
   └─ /odom

Dual RPLIDAR
   ├─ Front LiDAR
   └─ Rear LiDAR
          ↓
Laser Scan Merger
          ↓
        /scan
          ↓
Cartographer
          ↓
        /map
          ↓
         RViz
```

RViz에서 맵이 실시간으로 생성되는 것을 확인하면서 AMR을 움직인다.

정상적인 경우 대회 때와 비슷하게 대략:

```text
/odom ≈ 50 Hz
/scan ≈ 10 Hz
```

정도가 들어온다.

확인하려면:

```bash
ros2 topic hz /odom
```

```bash
ros2 topic hz /scan
```

---

## 1-3. 생성된 맵 저장

**Mapping launch는 켜둔 상태에서** 새 터미널을 연다.

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash
```

맵 저장:

```bash
ros2 run nav2_map_server map_saver_cli \
    -f ~/ros2_ws/src/amr/map/demo_map
```

성공하면:

```text
Map saved successfully
```

가 출력된다.

생성 파일:

```text
~/ros2_ws/src/amr/map/demo_map.pgm
~/ros2_ws/src/amr/map/demo_map.yaml
```

확인:

```bash
ls -lh ~/ros2_ws/src/amr/map/demo_map*
```

```bash
cat ~/ros2_ws/src/amr/map/demo_map.yaml
```

저장 완료 후 Mapping 터미널은:

```text
Ctrl + C
```

로 종료한다.

---

## 1-4. Waypoint Editor 실행

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash
```

```bash
ros2 run robocup_navigator waypoint_editor \
    --map ~/ros2_ws/src/amr/map/demo_map.yaml \
    --waypoints ~/ros2_ws/src/robocup_navigator/params/demo_waypoint.yaml
```

현재 demo에서는 다음 waypoint를 사용한다.

| Waypoint             | 의미              |
| -------------------- | --------------- |
| `station_0_goal`     | 시작점 / Home      |
| `station_1_sub_goal` | Station 1 접근 위치 |
| `station_1_goal`     | Station 1 최종 위치 |
| `station_2_sub_goal` | Station 2 접근 위치 |
| `station_2_goal`     | Station 2 최종 위치 |

Waypoint Editor에서는 원하는 waypoint를 선택한 다음:

```text
마우스 클릭 유지
      ↓
위치 지정
      ↓
마우스 드래그
      ↓
로봇 방향 지정
      ↓
마우스 놓기
```

방식으로 위치와 방향을 같이 설정한다.

마지막에는 반드시:

```text
Save
```

를 눌러서:

```text
demo_waypoint.yaml
```

에 저장한다.

현재 Station 구성은 개념적으로:

```yaml
stations:

  0:
    name: station_0
    sequence:
      - station_0_goal
    post_process: false

  1:
    name: station_1
    sequence:
      - station_1_sub_goal
      - station_1_goal
    post_process: false

  2:
    name: station_2
    sequence:
      - station_2_sub_goal
      - station_2_goal
    post_process: false
```

형태이다.

---

# 2. 주행 테스트 명령어

## 2-1. Demo Navigation 전체 실행

터미널 1:

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch all_in_one_package demo_all_in_one_launch.py
```

현재 만든 `demo_all_in_one_launch.py`는:

```text
demo_map.yaml
```

을 사용하도록 기존 `all_in_one_launch.py`에서 분리한 버전이다.

실행 후 RViz에서 먼저:

```text
2D Pose Estimate
```

를 사용해서 실제 AMR의 현재 위치와 방향을 지정한다.

즉:

```text
실제 AMR 위치
       ↓
RViz 2D Pose Estimate
       ↓
AMCL 초기 위치 지정
```

이다.

---

## 2-2. Station Navigator 실행

터미널 2:

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash
```

```bash
ros2 run robocup_navigator robocup_navigator_nav2 \
    --ros-args \
    -p stations_file:=/home/st02/ros2_ws/src/robocup_navigator/params/demo_waypoint.yaml
```

정상적으로 실행되면 Navigator가:

```text
Station 0
Station 1
Station 2
```

를 읽는다.

Action server 확인:

```bash
ros2 action list | grep navigate_to_station
```

정상이면:

```text
/navigate_to_station
```

이 보여야 한다.

---

## 2-3. 각각 수동 주행 테스트

### Station 1 Sub Goal

```bash
ros2 action send_goal \
    /navigate_to_station \
    robocup_pkg/action/NavTask \
    "{station_id: -1}" \
    --feedback
```

### Station 1 Goal

```bash
ros2 action send_goal \
    /navigate_to_station \
    robocup_pkg/action/NavTask \
    "{station_id: 1}" \
    --feedback
```

### Station 2 Sub Goal

```bash
ros2 action send_goal \
    /navigate_to_station \
    robocup_pkg/action/NavTask \
    "{station_id: -2}" \
    --feedback
```

### Station 2 Goal

```bash
ros2 action send_goal \
    /navigate_to_station \
    robocup_pkg/action/NavTask \
    "{station_id: 2}" \
    --feedback
```

### Home / Start 복귀

```bash
ros2 action send_goal \
    /navigate_to_station \
    robocup_pkg/action/NavTask \
    "{station_id: 0}" \
    --feedback
```

---

## 2-4. 자동 전체 주행

현재 만든 `demo_route`를 사용하면:

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 run robocup_navigator demo_route
```

한 번으로 전체 sequence를 실행할 수 있다.

현재 route:

```python
route = [-1, 1, -2, 2, 0]
```

따라서 실제 동작은:

```text
Start
  ↓
Station 1 Sub Goal
  ↓
Station 1 Goal
  ↓
Station 2 Sub Goal
  ↓
Station 2 Goal
  ↓
Home / Start
```

이 된다.

---

# 3. Waypoint Flow별 동작

현재 `robocup_navigator_nav2`에서는 **station ID의 부호가 의미를 가진다.**

|   명령 | 실제 Waypoint          | 역할              |
| ---: | -------------------- | --------------- |
|  `0` | `station_0_goal`     | Home / Start    |
| `-1` | `station_1_sub_goal` | Station 1 접근    |
|  `1` | `station_1_goal`     | Station 1 최종 접근 |
| `-2` | `station_2_sub_goal` | Station 2 접근    |
|  `2` | `station_2_goal`     | Station 2 최종 접근 |

즉:

```text
station_id < 0
      ↓
Sub Goal 이동

station_id >= 0
      ↓
Goal 이동
```

형태로 사용한다.

현재 전체 Flow는:

```text
[Start]
station_0_goal
      │
      │ -1
      ▼
[Station 1 Sub]
station_1_sub_goal
      │
      │ 1
      ▼
[Station 1 Goal]
station_1_goal
      │
      │ -2
      ▼
[Station 2 Sub]
station_2_sub_goal
      │
      │ 2
      ▼
[Station 2 Goal]
station_2_goal
      │
      │ 0
      ▼
[Start / Home]
station_0_goal
```

각 waypoint에서 실제 동작 명령은:

```text
demo_route
    │
    │ station_id
    ▼
robocup_navigator_nav2
    │
    │ Station ID → x,y,yaw 변환
    ▼
Nav2
    │
    ├─ AMCL       : 현재 위치 추정
    ├─ Planner    : 경로 생성
    ├─ Controller : 경로 추종
    └─ Recovery   : 실패 시 복구
    │
    ▼
/cmd_vel
    │
    ▼
serial_test
    │
    ▼
Motor
```

---

## 현재까지 완성된 범위

```text
새 공간 Mapping                ✅
Map PGM/YAML 저장              ✅
Station 0/1/2 지정             ✅
Sub Goal / Goal 방향 지정       ✅
AMCL Localization              ✅
Nav2 Navigation                ✅
Station Navigator              ✅
개별 Station 명령              ✅
자동 Sequence 주행             ✅
Home 복귀                      ✅
```

여기까지가 지금 말한 **“단순 주행 단계”**야.

다음 단계부터는 이 위에 **작업 명령 / Order / Planner / 로봇팔 작업을 결합해서 `어디로 갈지 + 가서 무엇을 할지`를 연결하는 단계**로 넘어가면 된다.

