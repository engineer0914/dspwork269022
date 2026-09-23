
---

# RoboCup AMR Manipulation 단독 동작 정리

## 1. 시스템 구성

기존 RoboCup 대회용 Manipulation Stack을 그대로 사용한다.

```text
amr_robot.launch.py
│
├── vision_node
│   └── /get_target_pose
│
├── gripper_node
│   ├── /gripper/open
│   ├── /gripper/grip
│   ├── /gripper/grip100
│   ├── /gripper/grip110
│   └── /gripper/grip120
│
├── cargo_manager_node
│   └── /cargo
│
└── amr_robot_node
    └── /amr_robot_command
```

`/amr_robot_command`에서 사용하는 명령은:

```text
LOAD
UNLOAD
ASSEMBLE
```

이다.

---

# 2. 로봇 네트워크 확인

RB5 Robot IP:

```text
10.0.2.8
```

현재 PC Ethernet IP:

```text
10.0.2.13
```

같은 `10.0.2.x/24` 대역이어야 한다.

연결 확인:

```bash
ping -c 4 10.0.2.8
```

정상 예:

```text
64 bytes from 10.0.2.8
0% packet loss
```

---

# 3. Manipulation Stack 실행

터미널 1:

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch amr_robot_launch amr_robot.launch.py
```

정상적으로 연결되면:

```text
[AMR] robot connected: 10.0.2.8
[AMR] data channel connected: 10.0.2.8
[AMR] amr_robot_node started
[AMR] moving pose reached
```

가 출력된다.

---

# 4. Manipulation 서비스 확인

터미널 2:

```bash
cd ~/ros2_ws

source /opt/ros/humble/setup.bash
source install/setup.bash
```

서비스 확인:

```bash
ros2 service list | grep -E "amr_robot|target_pose|gripper|cargo"
```

핵심 서비스:

```text
/amr_robot_command
/get_target_pose
/cargo
/gripper/open
/gripper/grip
/gripper/grip100
/gripper/grip110
/gripper/grip120
```

Robot IP 확인:

```bash
ros2 param get /amr_robot_node robot_ip
```

정상:

```text
String value is: 10.0.2.8
```

ArmCommand 구조 확인:

```bash
ros2 interface show robocup_pkg/srv/ArmCommand
```

```text
string action
int32[] object_ids
int32 location
int32 station_id
int32[] slide_ids
---
bool success
int32[] slots
int32[] object_ids
string message
```

---

# 5. 사용한 Object ID

이번 Magnet 데모에서 사용하는 ID:

```text
1  = 2x2 Red
3  = 2x2 Blue

13 = Magnet
```

Magnet 조립 순서:

```text
2x2 Red
   ↓
2x2 Blue
   ↓
Magnet
```

즉:

```text
Magnet product_id = 13

ASSEMBLY_SEQUENCE:
13 → [1, 3]
```

---

# 6. Blue 2x2 LOAD

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'LOAD', object_ids: [3], location: 1, station_id: 1, slide_ids: []}"
```

실제 성공 결과:

```text
success=True
slots=[2]
object_ids=[3]
message='load success'
```

결과:

```text
Cargo Slot 2
└── Blue 2x2
```

---

# 7. Red 2x2 LOAD

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'LOAD', object_ids: [1], location: 1, station_id: 1, slide_ids: []}"
```

실제 성공 결과:

```text
success=True
slots=[3]
object_ids=[1]
message='load success'
```

결과:

```text
Cargo Slot 2 → Blue 2x2
Cargo Slot 3 → Red 2x2
```

LOAD 내부에서는:

```text
Vision Pose 이동
        ↓
Brick 탐색
        ↓
Pick
        ↓
Gripper
        ↓
Cargo 빈 Slot 탐색
        ↓
Cargo 적재
```

가 자동으로 수행된다.

---

# 8. Magnet ASSEMBLE

Red와 Blue가 Cargo에 적재된 상태에서:

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'ASSEMBLE', object_ids: [13], location: 0, station_id: 0, slide_ids: []}"
```

여기서 중요한 점:

```text
object_ids = [1, 3]  X

object_ids = [13]    O
```

`ASSEMBLE`의 `object_ids`에는 재료가 아니라 **완성할 Product ID**를 넣는다.

내부에서는:

```text
Product 13 요청
      ↓
Recipe [1, 3] 조회
      ↓
Cargo에서 Red(1) 탐색
      ↓
Assembly Slot 7/8에 배치
      ↓
Cargo에서 Blue(3) 탐색
      ↓
Red 위에 결합
      ↓
Magnet 완성
```

조립 슬롯은 자동으로:

```text
7 → 8
```

순서로 빈 곳을 배정한다.

이번 테스트에서는 실제로 Magnet이 조립되어 Assembly Cargo 한쪽에 생성되는 것을 확인했다.

---

# 9. Magnet UNLOAD

완성된 Magnet을 내려놓기:

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'UNLOAD', object_ids: [13], location: 0, station_id: 2, slide_ids: []}"
```

실제 성공 결과:

```text
success=True
slots=[7]
object_ids=[13]
message='unload success'
```

`station_id=2`는 기존 코드의 Workbench ID가 아니다.

기존 Workbench:

```text
WORKBENCH_STATION_IDS = {4, 10}
```

따라서 `station_id=2`에서는:

```text
Cargo Assembly Slot에서 Magnet Pick
        ↓
Delivery Point 6 부근 이동
        ↓
Vision target 666
        ↓
빈 공간 탐색
        ↓
x, y 위치 보정
        ↓
Magnet 내려놓기
```

동작을 수행한다.

---

# 10. 이번에 검증된 전체 Manipulation Flow

```text
Blue 2x2
   │
   │ LOAD [3]
   ▼
Cargo Slot

Red 2x2
   │
   │ LOAD [1]
   ▼
Cargo Slot
   │
   │
   └──────────────┐
                  ▼
          ASSEMBLE [13]
                  │
                  ▼
             Magnet
                  │
        Assembly Slot 7/8
                  │
                  │ UNLOAD [13]
                  ▼
             제출 위치
```

실제 하드웨어 기준 결과:

```text
LOAD Blue       ✅
LOAD Red        ✅
ASSEMBLE Magnet ✅
UNLOAD Magnet   ✅
```

---

# 11. 최소 실행 명령만 모아서 보기

### Manipulation 실행

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch amr_robot_launch amr_robot.launch.py
```

### Blue LOAD

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'LOAD', object_ids: [3], location: 1, station_id: 1, slide_ids: []}"
```

### Red LOAD

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'LOAD', object_ids: [1], location: 1, station_id: 1, slide_ids: []}"
```

### Magnet ASSEMBLE

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'ASSEMBLE', object_ids: [13], location: 0, station_id: 0, slide_ids: []}"
```

### Magnet UNLOAD

```bash
ros2 service call /amr_robot_command \
  robocup_pkg/srv/ArmCommand \
  "{action: 'UNLOAD', object_ids: [13], location: 0, station_id: 2, slide_ids: []}"
```

---

현재까지를 한 줄로 정리하면:

```text
기존 대회 Manipulation 코드는 수정 없이 그대로 사용 가능하며,
LOAD → ASSEMBLE → UNLOAD 전체 과정이 실제 하드웨어에서 검증됨.
```

이제 다음 단계에서는 **매니퓰레이션 쪽은 건드리지 않고**, 다시 `demo_map + station 0/1/2`부터 정리해서 Navigation과 이 네 명령을 연결하면 돼.

