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

        # Navigation
        self.nav_client = ActionClient(
            self,
            NavTask,
            '/navigate_to_station'
        )

        # Manipulation
        self.arm_client = self.create_client(
            ArmCommand,
            '/amr_robot_command'
        )

    # ============================================================
    # Navigation
    # ============================================================

    def navigate(self, station_id: int) -> bool:
        self.get_logger().info(
            f'========================================'
        )
        self.get_logger().info(
            f'[NAV] Moving to station_id={station_id}'
        )
        self.get_logger().info(
            f'========================================'
        )

        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                '[NAV] /navigate_to_station action server not available'
            )
            return False

        goal = NavTask.Goal()
        goal.station_id = int(station_id)

        send_future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()

        if goal_handle is None:
            self.get_logger().error('[NAV] Failed to send goal')
            return False

        if not goal_handle.accepted:
            self.get_logger().error(
                f'[NAV] Goal rejected: station_id={station_id}'
            )
            return False

        self.get_logger().info(
            f'[NAV] Goal accepted: station_id={station_id}'
        )

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        wrapped_result = result_future.result()

        if wrapped_result is None:
            self.get_logger().error(
                f'[NAV] No result: station_id={station_id}'
            )
            return False

        if wrapped_result.status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f'[NAV] Failed: station_id={station_id}, '
                f'status={wrapped_result.status}'
            )
            return False

        self.get_logger().info(
            f'[NAV] ARRIVED station_id={station_id}'
        )

        return True

    # ============================================================
    # Manipulation
    # ============================================================

    def arm_command(
        self,
        action: str,
        object_ids,
        station_id: int = 0,
        location: int = 0
    ) -> bool:

        self.get_logger().info(
            f'========================================'
        )
        self.get_logger().info(
            f'[ARM] {action} objects={object_ids}, '
            f'station={station_id}'
        )
        self.get_logger().info(
            f'========================================'
        )

        if not self.arm_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(
                '[ARM] /amr_robot_command service not available'
            )
            return False

        req = ArmCommand.Request()

        req.action = str(action)
        req.object_ids = [int(x) for x in object_ids]
        req.location = int(location)
        req.station_id = int(station_id)
        req.slide_ids = []

        future = self.arm_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

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
            f'[ARM] {action} SUCCESS'
        )
        self.get_logger().info(
            f'[ARM] object_ids={list(response.object_ids)}'
        )
        self.get_logger().info(
            f'[ARM] slots={list(response.slots)}'
        )
        self.get_logger().info(
            f'[ARM] message={response.message}'
        )

        return True

    # ============================================================
    # Demo Sequence
    # ============================================================

    def run_demo(self) -> bool:

        self.get_logger().info('')
        self.get_logger().info(
            '########################################'
        )
        self.get_logger().info(
            '# SIMPLE E-STOP DEMO START'
        )
        self.get_logger().info(
            '########################################'
        )

        # --------------------------------------------------------
        # STEP 1
        # Station 1 Goal
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 1] Move directly to Station 1 Goal'
        )

        if not self.navigate(1):
            return False

        time.sleep(1.0)

        # --------------------------------------------------------
        # STEP 2
        # LOAD materials for E-stop
        #
        # E-stop 81 = [8, 1]
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 2] LOAD materials [8, 1]'
        )

        if not self.arm_command(
            action='LOAD',
            object_ids=[8, 1],
            station_id=1,
            location=1
        ):
            return False

        # --------------------------------------------------------
        # STEP 3
        # Move to Station 2 Sub Goal
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 3] Move to Station 2 Sub Goal'
        )

        if not self.navigate(-2):
            return False

        # --------------------------------------------------------
        # STEP 4
        # Move to Station 2 Goal
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 4] Move to Station 2 Goal'
        )

        if not self.navigate(2):
            return False

        time.sleep(1.0)

        # --------------------------------------------------------
        # STEP 5
        # ASSEMBLE E-stop
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 5] ASSEMBLE E-stop 81'
        )

        if not self.arm_command(
            action='ASSEMBLE',
            object_ids=[81],
            station_id=0,
            location=0
        ):
            return False

        # --------------------------------------------------------
        # STEP 6
        # UNLOAD E-stop
        #
        # station_id=2:
        # finished-product delivery using vision empty-space path
        # --------------------------------------------------------

        self.get_logger().info(
            '[STEP 6] UNLOAD E-stop 81 at Station 2'
        )

        if not self.arm_command(
            action='UNLOAD',
            object_ids=[81],
            station_id=2,
            location=0
        ):
            return False

        # --------------------------------------------------------

        self.get_logger().info('')
        self.get_logger().info(
            '########################################'
        )
        self.get_logger().info(
            '# SIMPLE E-STOP DEMO COMPLETE'
        )
        self.get_logger().info(
            '########################################'
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
            'Demo interrupted by user'
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
