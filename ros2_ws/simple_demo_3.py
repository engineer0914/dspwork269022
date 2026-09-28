#!/usr/bin/env python3

import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from action_msgs.msg import GoalStatus

from robocup_pkg.action import NavTask
from robocup_pkg.srv import ArmCommand


class SimpleDemo(Node):

    def __init__(self):
        super().__init__('simple_demo')

        # Navigation Action
        self.nav_client = ActionClient(
            self,
            NavTask,
            '/navigate_to_station'
        )

        # Robot Arm Service
        self.arm_client = self.create_client(
            ArmCommand,
            '/amr_robot_command'
        )


    # ============================================================
    # Navigation
    # ============================================================

    def navigate(self, station_id: int) -> bool:

        self.get_logger().info(
            f'[NAV] Moving to station_id={station_id}'
        )

        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                '[NAV] /navigate_to_station not available'
            )
            return False

        goal = NavTask.Goal()
        goal.station_id = int(station_id)

        send_future = self.nav_client.send_goal_async(goal)

        rclpy.spin_until_future_complete(
            self,
            send_future
        )

        goal_handle = send_future.result()

        if goal_handle is None:
            self.get_logger().error(
                '[NAV] Failed to send goal'
            )
            return False

        if not goal_handle.accepted:
            self.get_logger().error(
                f'[NAV] Goal rejected: {station_id}'
            )
            return False

        self.get_logger().info(
            f'[NAV] Goal accepted: {station_id}'
        )

        result_future = goal_handle.get_result_async()

        rclpy.spin_until_future_complete(
            self,
            result_future
        )

        wrapped_result = result_future.result()

        if wrapped_result is None:
            self.get_logger().error(
                f'[NAV] No result: {station_id}'
            )
            return False

        if wrapped_result.status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f'[NAV] Failed station={station_id}, '
                f'status={wrapped_result.status}'
            )
            return False

        self.get_logger().info(
            f'[NAV] ARRIVED station={station_id}'
        )

        return True


    # ============================================================
    # Normal synchronous ARM command
    # LOAD / UNLOAD용
    # ============================================================

    def arm_command(
        self,
        action: str,
        object_ids,
        station_id: int = 0,
        location: int = 0
    ) -> bool:

        self.get_logger().info(
            f'[ARM] {action} objects={object_ids}'
        )

        if not self.arm_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(
                '[ARM] /amr_robot_command not available'
            )
            return False

        req = ArmCommand.Request()

        req.action = str(action)
        req.object_ids = [int(x) for x in object_ids]
        req.location = int(location)
        req.station_id = int(station_id)
        req.slide_ids = []

        future = self.arm_client.call_async(req)

        rclpy.spin_until_future_complete(
            self,
            future
        )

        response = future.result()

        if response is None:
            self.get_logger().error(
                f'[ARM] No response: {action}'
            )
            return False

        if not response.success:
            self.get_logger().error(
                f'[ARM] {action} FAILED: {response.message}'
            )
            return False

        self.get_logger().info(
            f'[ARM] {action} SUCCESS '
            f'objects={list(response.object_ids)} '
            f'slots={list(response.slots)}'
        )

        return True


    # ============================================================
    # ASYNC ARM START
    #
    # 조립을 요청하지만 여기서는 기다리지 않는다.
    # AMR Navigation과 동시에 동작시키기 위함.
    # ============================================================

    def start_arm_async(
        self,
        action: str,
        object_ids,
        station_id: int = 0,
        location: int = 0
    ):

        self.get_logger().info(
            f'[ARM ASYNC START] {action} objects={object_ids}'
        )

        if not self.arm_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(
                '[ARM] /amr_robot_command not available'
            )
            return None

        req = ArmCommand.Request()

        req.action = str(action)
        req.object_ids = [int(x) for x in object_ids]
        req.location = int(location)
        req.station_id = int(station_id)
        req.slide_ids = []

        # 여기서는 결과를 기다리지 않는다.
        future = self.arm_client.call_async(req)

        return future


    # ============================================================
    # ASYNC ARM WAIT
    #
    # 앞에서 시작한 조립이 끝났는지 여기서 기다린다.
    # ============================================================

    def wait_arm_async(
        self,
        future,
        action_name='ASSEMBLE'
    ) -> bool:

        if future is None:
            self.get_logger().error(
                f'[ARM ASYNC] Invalid future: {action_name}'
            )
            return False

        self.get_logger().info(
            f'[ARM ASYNC WAIT] Waiting for {action_name}'
        )

        rclpy.spin_until_future_complete(
            self,
            future
        )

        response = future.result()

        if response is None:
            self.get_logger().error(
                f'[ARM ASYNC] No response: {action_name}'
            )
            return False

        if not response.success:
            self.get_logger().error(
                f'[ARM ASYNC] {action_name} FAILED: '
                f'{response.message}'
            )
            return False

        self.get_logger().info(
            f'[ARM ASYNC] {action_name} SUCCESS '
            f'objects={list(response.object_ids)} '
            f'slots={list(response.slots)}'
        )

        return True


    # ============================================================
    # Demo Sequence
    # ============================================================

    def run_demo(self) -> bool:

        self.get_logger().info('')
        self.get_logger().info(
            '============================================'
        )
        self.get_logger().info(
            ' SIMPLE TRAFFIC LIGHT DEMO START'
        )
        self.get_logger().info(
            '============================================'
        )


        # ========================================================
        # STEP 1
        # Station 1 Goal
        # ========================================================

        self.get_logger().info(
            '[STEP 1] Move to Station 1 Goal'
        )

        if not self.navigate(1):
            return False


        # ========================================================
        # STEP 2
        # LOAD
        #
        # Traffic Light recipe:
        #
        # 241 = [2, 4, 1]
        #
        # 2 = 2x2 Green
        # 4 = 2x2 Yellow
        # 1 = 2x2 Red
        # ========================================================

        self.get_logger().info(
            '[STEP 2] LOAD [8, 1]'
        )

        if not self.arm_command(
            action='LOAD',
            object_ids=[2, 4, 1],
            station_id=1,
            location=1
        ):
            return False


        # ========================================================
        # STEP 3
        #
        # Traffic Light 조립을 먼저 비동기로 시작한다.
        #
        # 여기서 기다리지 않는다.
        # ========================================================

        self.get_logger().info(
            '[STEP 3] Start Traffic Light assembly ASYNC'
        )

        assemble_future = self.start_arm_async(
            action='ASSEMBLE',
            object_ids=[241],
            station_id=0,
            location=0
        )

        if assemble_future is None:
            return False


        # ========================================================
        # STEP 4
        #
        # 조립 중 동시에 Station 2 Sub Goal 이동
        # ========================================================

        self.get_logger().info(
            '[STEP 4] Move to Station 2 Sub Goal '
            'while assembling Traffic Light'
        )

        if not self.navigate(-2):
            return False


        # ========================================================
        # STEP 5
        #
        # B Sub Goal에 도착했지만,
        # 조립이 아직 안 끝났다면 여기서 기다린다.
        #
        # 조립이 이미 끝났다면 즉시 통과.
        # ========================================================

        self.get_logger().info(
            '[STEP 5] Check Traffic Light assembly'
        )

        if not self.wait_arm_async(
            assemble_future,
            'ASSEMBLE TRAFFIC LIGHT 241'
        ):
            return False


        # ========================================================
        # STEP 6
        #
        # 조립이 완전히 끝난 상태에서
        # B 정밀 위치로 진입
        # ========================================================

        self.get_logger().info(
            '[STEP 6] Move to Station 2 Goal'
        )

        if not self.navigate(2):
            return False


        # ========================================================
        # STEP 7
        #
        # 완성된 Traffic Light 내려놓기
        #
        # station_id=2:
        # Vision 666 기반 빈 공간 탐색
        # ========================================================

        self.get_logger().info(
            '[STEP 7] UNLOAD Traffic Light 81'
        )

        if not self.arm_command(
            action='UNLOAD',
            object_ids=[241],
            station_id=2,
            location=0
        ):
            return False


        self.get_logger().info('')
        self.get_logger().info(
            '============================================'
        )
        self.get_logger().info(
            ' SIMPLE TRAFFIC LIGHT DEMO COMPLETE'
        )
        self.get_logger().info(
            '============================================'
        )

        return True


def main(args=None):

    rclpy.init(args=args)

    node = SimpleDemo()

    try:

        success = node.run_demo()

        if not success:
            node.get_logger().error(
                'DEMO ABORTED'
            )
            sys.exit(1)

    except KeyboardInterrupt:

        node.get_logger().warn(
            'Demo interrupted'
        )

    except Exception as e:

        node.get_logger().error(
            f'Demo exception: {e}'
        )

        raise

    finally:

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
