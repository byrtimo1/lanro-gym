import numpy as np
from lanro.robots import PyBulletRobot
from lanro.simulation import PyBulletSimulation
from lanro.tasks.core import LanguageTask
from lanro.tasks.scene import basic_scene
from lanro.utils import goal_distance


class NLPush(LanguageTask):

    def __init__(self,
                 sim: PyBulletSimulation,
                 robot: PyBulletRobot,
                 obj_xy_range: float = 0.3,
                 num_obj: int = 2,
                 use_hindsight_instructions: bool = False,
                 mode: str = 'Color'):
        super().__init__(sim, robot, mode, use_hindsight_instructions, num_obj)
        self.min_push_distance = 0.025
        self.max_push_distance = 0.075
        self.max_height_change = self.object_size
        self.obj_range_low = np.array([-obj_xy_range / 2, -obj_xy_range / 2, 0])
        self.obj_range_high = np.array([obj_xy_range / 2, obj_xy_range / 2, 0])
        self.action_verbs = ["push", "move", "shift"]
        with self.sim.no_rendering():
            self._create_scene()
            self.sim.place_visualizer()

    def _create_scene(self) -> None:
        basic_scene(self.sim)

    def show_goal_boundary(self):
        if self.sim.render_on:
            self.sim.remove_body('target')
            target_pos = self.obj_init_pos_dict[self.goal_object_body_key]
            target_pos[-1] = 0
            self.sim.create_cylinder(
                body_name="target",
                mass=0.0,
                ghost=True,
                radius=self.ep_push_distance,
                height=0.001,
                position=target_pos,
                rgba_color=self.task_object_list.objects[self.goal_obj_idx].get_color().value + [0.3],
            )

    def reset(self) -> None:
        self.obj_init_pos_dict = {}
        self.sample_task_objects()
        self.obj_init_pos = self._sample_objects()
        for idx, obj_pos in zip(self.obj_indices_selection, self.obj_init_pos):
            obj_key = f"object{idx}"
            self.sim.set_base_pose(obj_key, obj_pos.tolist(), [0, 0, 0, 1])
            self.obj_init_pos_dict[obj_key] = np.array(obj_pos)
        self._sample_goal()
        self.ep_push_distance = self.np_random.uniform(low=self.min_push_distance, high=self.max_push_distance)
        # visualize goal region
        self.show_goal_boundary()
        self.reset_hi()

    def is_success(self):
        init_goal_pos = self.obj_init_pos_dict[self.goal_object_body_key]
        current_goal_pos = np.array(self.sim.get_base_position(self.goal_object_body_key))
        return self.detect_push_motion(init_goal_pos, current_goal_pos)

    def detect_push_motion(self, inital_pos, current_pos) -> bool:
        assert len(inital_pos) == 3
        assert len(current_pos) == 3
        change_xy = goal_distance(inital_pos[:2], current_pos[:2])
        change_z = goal_distance(inital_pos[-1:], current_pos[-1:])
        # let change only happen for x and y, and keep z as close as possible
        # this should prevent lifting the object or throwing it to the ground
        return change_xy > self.ep_push_distance and change_z < self.max_height_change

    def moved_other_object(self) -> str:
        for other_object_idx in self.non_goal_body_indices:
            _non_goal_body = f"object{other_object_idx}"
            init_obj_pos = self.obj_init_pos_dict[_non_goal_body]
            current_obj_pos = np.array(self.sim.get_base_position(_non_goal_body))
            if self.detect_push_motion(init_obj_pos, current_obj_pos):
                return other_object_idx
        else:
            return ''

    def compute_reward(self) -> float:
        if self.is_success():
            return 0.0
        elif self.ep_hindsight_instruction and not self.ep_hindsight_instruction_returned:
            other_object_idx = self.moved_other_object()
            if other_object_idx:
                self.generate_hindsight_instruction(other_object_idx)
                return -10.
        return -1.0
