#!/usr/bin/env python3
"""완제품 하나를 Station 1에서 가져와 Station 2에 내려놓는다.

실행:
    python3 bring.py 13
    python3 bring.py 48132
"""

import argparse
import sys

import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from robocup_pkg.action import NavTask
from robocup_pkg.srv import ArmCommand


# LOAD / UNLOAD 동작이 확인된 완제품 ID.
SUPPORTED_PRODUCT_IDS = (
    34, 13, 81, 442, 241, 462, 711, 4482, 48132, 46262,
)


def parse_product_args(argv):
    parser = argparse.ArgumentParser(
        description="완제품을 Station 1에서 가져와 Station 2에 하역합니다.",
        epilog="지원 ID: " + ", ".join(map(str, SUPPORTED_PRODUCT_IDS)),
    )
    parser.add_argument(
        "product_id",
        type=int,
        help="가져올 완제품 ID. 예: 13",
    )
    options = parser.parse_args(argv)

    if options.product_id not in SUPPORTED_PRODUCT_IDS:
        parser.error(
            f"지원하지 않는 제품 ID: {options.product_id}. "
            "지원 ID: " + ", ".join(map(str, SUPPORTED_PRODUCT_IDS))
        )

    return options


class BringProduct(Node):
    def __init__(self, product_id: int):
        super().__init__("bring_product")
        self.product_id = product_id

        self.nav_client = ActionClient(
            self, NavTask, "/navigate_to_station"
        )
        self.arm_client = self.create_client(
            ArmCommand, "/amr_robot_command"
        )

    def navigate(self, station_id: int) -> bool:
        self.get_logger().info(
            f"[NAV] Moving to station_id={station_id}"
        )

        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                "[NAV] /navigate_to_station not available"
            )
            return False

        goal = NavTask.Goal()
        goal.station_id = int(station_id)

        send_future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if goal_handle is None:
            self.get_logger().error("[NAV] Failed to send goal")
            return False

        if not goal_handle.accepted:
            self.get_logger().error(
                f"[NAV] Goal rejected: {station_id}"
            )
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        wrapped_result = result_future.result()

        if wrapped_result is None:
            self.get_logger().error(
                f"[NAV] No result: {station_id}"
            )
            return False

        if wrapped_result.status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f"[NAV] Failed station={station_id}, "
                f"status={wrapped_result.status}"
            )
            return False

        self.get_logger().info(
            f"[NAV] ARRIVED station={station_id}"
        )
        return True

    def arm_command(
        self,
        action: str,
        station_id: int,
        location: int,
    ) -> bool:
        # 제품 ID 전체를 하나의 object_id로 전달한다.
        # 13 -> [13], 48132 -> [48132]
        object_ids = [self.product_id]

        self.get_logger().info(
            f"[ARM] {action} objects={object_ids}, "
            f"station={station_id}, location={location}"
        )

        if not self.arm_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(
                "[ARM] /amr_robot_command not available"
            )
            return False

        req = ArmCommand.Request()
        req.action = action
        req.object_ids = object_ids
        req.location = int(location)
        req.station_id = int(station_id)
        req.slide_ids = []

        future = self.arm_client.call_async(req)

        # LOAD / UNLOAD 완료 응답까지 기다린다.
        rclpy.spin_until_future_complete(self, future)
        response = future.result()

        if response is None:
            self.get_logger().error(
                f"[ARM] No response: {action}"
            )
            return False

        if not response.success:
            self.get_logger().error(
                f"[ARM] {action} FAILED: {response.message}"
            )
            return False

        self.get_logger().info(
            f"[ARM] {action} SUCCESS "
            f"objects={list(response.object_ids)} "
            f"slots={list(response.slots)}"
        )
        return True

    def run_demo(self) -> bool:
        self.get_logger().info(
            f"=== BRING START: product_id={self.product_id} ==="
        )

        # 출발 전에 이동 액션과 로봇팔 서비스 연결 확인.
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error(
                "[NAV] /navigate_to_station not available"
            )
            return False

        if not self.arm_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error(
                "[ARM] /amr_robot_command not available"
            )
            return False

        self.get_logger().info("[STEP 1] Move to Station 1")
        if not self.navigate(1):
            return False

        # 기존 LOAD 서비스가 제품 탐색·집기·적재를 수행한다.
        self.get_logger().info(
            f"[STEP 2] LOAD finished product [{self.product_id}]"
        )
        if not self.arm_command(
            action="LOAD", station_id=1, location=1
        ):
            return False

        # 적재 성공 후 이동을 시작한다.
        self.get_logger().info(
            "[STEP 3] Move to Station 2 Sub Goal (-2)"
        )
        if not self.navigate(-2):
            return False

        self.get_logger().info("[STEP 4] Move to Station 2")
        if not self.navigate(2):
            return False

        self.get_logger().info(
            f"[STEP 5] UNLOAD finished product [{self.product_id}]"
        )
        if not self.arm_command(
            action="UNLOAD", station_id=2, location=0
        ):
            return False

        self.get_logger().info(
            f"=== BRING COMPLETE: product_id={self.product_id} ==="
        )
        return True


def main(args=None):
    argv = list(sys.argv[1:] if args is None else args)
    cli_args = remove_ros_args(args=["bring.py"] + argv)[1:]
    options = parse_product_args(cli_args)

    # 제품 ID 검증을 마친 뒤 ROS를 초기화한다.
    rclpy.init(args=argv)
    node = None

    try:
        node = BringProduct(options.product_id)

        if not node.run_demo():
            node.get_logger().error(
                f"BRING ABORTED: product_id={node.product_id}"
            )
            return 1

        return 0

    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().warning(
                "Bring interrupted; already submitted robot "
                "commands may still be running."
            )
        return 130

    except Exception as exc:
        if node is not None:
            node.get_logger().error(f"Bring exception: {exc}")
        else:
            print(
                f"Bring initialization failed: {exc}",
                file=sys.stderr,
            )
        return 1

    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
