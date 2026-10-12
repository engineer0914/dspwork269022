#!/usr/bin/env python3
# 제품 ID 하나를 받아 브릭 적재 → 이동 중 조립 → 완제품 하역을 수행하는 ROS2 데모입니다.
# 등록된 제품 ID의 각 자릿수를 브릭 ID로 사용하며, 재료의 순서와 중복을 유지합니다.
# 실행 예: python3 simple_demo.py 46262 (Station 1 적재 → Station 2 Sub Goal 경유 → Station 2 하역)

import argparse
import sys

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.utilities import remove_ros_args

from action_msgs.msg import GoalStatus

from robocup_pkg.action import NavTask
from robocup_pkg.srv import ArmCommand


# User-confirmed products: each digit is one brick ID, in recipe order.
# Keep duplicates: 46262 requires [4, 6, 2, 6, 2], including two 6s and two 2s.
SUPPORTED_PRODUCT_IDS = (
    34, 13, 81, 711, 462, 241, 442, 4482, 48132, 46262, 8518,
)
PRODUCT_RECIPES = {
    product_id: [int(digit) for digit in str(product_id)]
    for product_id in SUPPORTED_PRODUCT_IDS
}

PRODUCT_NAMES = {
    241: 'Traffic Light',
    711: 'Hammer',
}


def valid_recipe(recipe):
    return (
        isinstance(recipe, (list, tuple))
        and bool(recipe)
        and all(type(object_id) is int and object_id > 0 for object_id in recipe)
    )


def supported_products():
    return ', '.join(
        f'{product_id} ({PRODUCT_NAMES.get(product_id, "Product")})'
        for product_id, recipe in sorted(PRODUCT_RECIPES.items())
        if valid_recipe(recipe)
    ) or '(none)'


def parse_product_args(argv):
    parser = argparse.ArgumentParser(
        description='Load, assemble in transit, and unload one product.',
        epilog=f'Supported product IDs: {supported_products()}',
    )
    parser.add_argument('product_id', type=int, help='Product ID to manufacture')
    options = parser.parse_args(argv)
    product_id = options.product_id
    if product_id not in PRODUCT_RECIPES:
        parser.error(
            f'Unsupported product_id={product_id}. '
            f'Supported product IDs: {supported_products()}'
        )
    if not valid_recipe(PRODUCT_RECIPES[product_id]):
        parser.error(
            f'Recipe for product_id={product_id} is missing or invalid. '
            f'Set PRODUCT_RECIPES[{product_id}] to a verified non-empty '
            f'list of positive integer block object_ids. '
            f'Supported product IDs: {supported_products()}'
        )
    return options


class SimpleDemo(Node):

    def __init__(self, product_id: int):
        if not valid_recipe(PRODUCT_RECIPES.get(product_id)):
            raise ValueError(f'Missing or invalid recipe for product_id={product_id}')
        self.product_id = product_id
        self.recipe = list(PRODUCT_RECIPES[product_id])
        self.product_label = f'{PRODUCT_NAMES.get(product_id, "Product")} {product_id}'
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
        self.get_logger().info(
            f'=== DEMO START: {self.product_label}, recipe={self.recipe} ==='
        )

        self.get_logger().info('[STEP 1] Move to Station 1 Goal')
        if not self.navigate(1):
            return False

        # LOAD keeps the existing arm service's block search/pick/load behavior.
        self.get_logger().info(
            f'[STEP 2] LOAD blocks={self.recipe} for {self.product_label}'
        )
        if not self.arm_command(
            action='LOAD', object_ids=self.recipe, station_id=1, location=1
        ):
            return False

        # Submit assembly without waiting; navigation spins the same ROS node
        # and can process the arm response while the robot is in transit.
        self.get_logger().info(
            f'[STEP 3] Start ASSEMBLE asynchronously: {self.product_label}'
        )
        assemble_future = self.start_arm_async(
            action='ASSEMBLE', object_ids=[self.product_id],
            station_id=0, location=0
        )
        if assemble_future is None:
            return False

        self.get_logger().info(
            f'[STEP 4] Move to Station 2 Sub Goal (-2) '
            f'while assembling {self.product_label}'
        )
        if not self.navigate(-2):
            self.get_logger().error(
                f'Navigation failed during ASSEMBLE {self.product_label}; '
                'the submitted arm service may still be running.'
            )
            return False

        # This also handles assembly that finished before arrival at -2.
        self.get_logger().info(
            f'[STEP 5] Wait for ASSEMBLE completion: {self.product_label}'
        )
        if not self.wait_arm_async(
            assemble_future, f'ASSEMBLE {self.product_label}'
        ):
            return False

        self.get_logger().info('[STEP 6] Move to Station 2 Goal (2)')
        if not self.navigate(2):
            return False

        self.get_logger().info(f'[STEP 7] UNLOAD {self.product_label}')
        if not self.arm_command(
            action='UNLOAD', object_ids=[self.product_id],
            station_id=2, location=0
        ):
            return False

        self.get_logger().info(f'=== DEMO COMPLETE: {self.product_label} ===')
        return True


def main(args=None):
    # args, when provided programmatically, excludes the executable name.
    argv = list(sys.argv[1:] if args is None else args)
    cli_args = remove_ros_args(args=['simple_demo.py'] + argv)[1:]
    options = parse_product_args(cli_args)

    # Validate the recipe BEFORE ROS initialization or any robot command.
    rclpy.init(args=argv)
    node = None
    try:
        node = SimpleDemo(options.product_id)
        if not node.run_demo():
            node.get_logger().error(f'DEMO ABORTED: {node.product_label}')
            return 1
        return 0
    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().warning(
                f'Demo interrupted: {node.product_label}; '
                'already submitted robot commands may still be running.'
            )
        return 130
    except Exception as exc:
        if node is not None:
            node.get_logger().error(
                f'Demo exception for {node.product_label}: {exc}'
            )
        else:
            print(f'Demo initialization failed: {exc}', file=sys.stderr)
        return 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())

