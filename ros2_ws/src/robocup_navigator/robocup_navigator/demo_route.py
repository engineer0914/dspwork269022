#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from robocup_pkg.action import NavTask


class DemoRoute(Node):

    def __init__(self):
        super().__init__('demo_route')

        self.client = ActionClient(
            self,
            NavTask,
            '/navigate_to_station'
        )

        # Start -> S1 sub -> S1 goal -> S2 sub -> S2 goal -> Start
        self.route = [-1, 1, -2, 2, 0]

    def run(self):

        self.get_logger().info(
            'Waiting for /navigate_to_station...'
        )

        self.client.wait_for_server()

        for station_id in self.route:

            self.get_logger().info(
                f'=== GO station_id={station_id} ==='
            )

            goal = NavTask.Goal()
            goal.station_id = station_id

            send_future = self.client.send_goal_async(
                goal,
                feedback_callback=self.feedback_callback
            )

            rclpy.spin_until_future_complete(self, send_future)

            goal_handle = send_future.result()

            if goal_handle is None or not goal_handle.accepted:
                self.get_logger().error(
                    f'Goal rejected: station_id={station_id}'
                )
                return False

            result_future = goal_handle.get_result_async()
            rclpy.spin_until_future_complete(self, result_future)

            wrapped_result = result_future.result()

            if wrapped_result is None:
                self.get_logger().error(
                    f'No result: station_id={station_id}'
                )
                return False

            result = wrapped_result.result

            if not result.success:
                self.get_logger().error(
                    f'Failed station_id={station_id}: '
                    f'{result.fail_reason}'
                )
                return False

            self.get_logger().info(
                f'=== ARRIVED station_id={station_id} ==='
            )

        self.get_logger().info(
            '===== DEMO ROUTE COMPLETE ====='
        )

        return True

    def feedback_callback(self, feedback_msg):

        feedback = feedback_msg.feedback

        try:
            self.get_logger().info(
                f'feedback: {feedback.status}'
            )
        except Exception:
            pass


def main(args=None):

    rclpy.init(args=args)

    node = DemoRoute()

    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
