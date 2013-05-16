from kivy.properties import (StringProperty, ListProperty, ObjectProperty, 
BooleanProperty, NumericProperty)
from gamesystems import GameSystem
import cymunk
import math


class CymunkPhysics(GameSystem):
    system_id = StringProperty('cymunk-physics')
    space = ObjectProperty(None)
    gravity = ListProperty((0, 0))
    updateable = BooleanProperty(True)
    iterations = NumericProperty(5)
    sleep_time_threshold = NumericProperty(.5)
    collision_slop = NumericProperty(.1)

    def __init__(self, **kwargs):
        super(CymunkPhysics, self).__init__(**kwargs)
        self.current_on_screen = list()
        self.init_physics()

    def init_physics(self):
        self.space = space = cymunk.Space()
        space.iterations = self.iterations
        space.gravity = self.gravity
        space.sleep_time_threshold = self.sleep_time_threshold
        
        space.collision_slop = self.collision_slop
        space.register_bb_query_func(self.bb_query_func)

    def test_bb_query(self, dt):
        viewport = self.gameworld.systems[self.viewport]
        camera_pos = viewport.camera_pos
        size = viewport.size
        bb_list = [camera_pos[0], camera_pos[1], size[0], size[1]]
        bb = cymunk.BB(bb_list[0], bb_list[1], bb_list[2], bb_list[3])
        self.space.space_bb_query_func(bb)

    def bb_query_func(self, shape):
        self.current_on_screen.append(shape.body.data)

    def query_on_screen(self):
        viewport = self.gameworld.systems[self.viewport]
        camera_pos = viewport.camera_pos
        size = viewport.size
        bb_list = [-camera_pos[0], -camera_pos[1], -camera_pos[0] + size[0], -camera_pos[1] + size[1]]
        bb = cymunk.BB(bb_list[0], bb_list[1], bb_list[2], bb_list[3])
        self.current_on_screen = []
        self.space.space_bb_query_func(bb)
        return self.current_on_screen
        

    def generate_component_data(self, entity_component_dict):
        '''entity_component_dict of the form {'entity_id': id, 'main_shape': string_shape_name, 
        'velocity': (x, y), 'position': (x, y), 'angle': radians, 
        'angular_velocity': radians, 'mass': float, col_shapes': [col_shape_dicts]}

        col_shape_dicts look like : {'shape_type': string_shape_name, 'elasticity': float, 
        'collision_type': int, 'shape_info': shape_specific_dict}

        shape_info:
        box: {'width': float, 'height': float, 'mass': float}
        circle: {'inner_radius': float, 'outer_radius': float, 'mass': float, 'offset': tuple}
        solid cirlces have an inner_radius of 0

        outputs component dict: {'body': body, 'shapes': array_of_shapes, 
        'position': body.position, angle': body.angle}

        '''
        shape = entity_component_dict['col_shapes'][0]

        if shape['shape_type'] == 'circle':
            moment = cymunk.moment_for_circle(shape['shape_info']['mass'], 
                shape['shape_info']['inner_radius'], shape['shape_info']['outer_radius'], 
                shape['shape_info']['offset'])
        elif shape['shape_type'] == 'box':
            moment = cymunk.moment_for_box(shape['shape_info']['mass'], 
                shape['shape_info']['width'], shape['shape_info']['height'])
        else:
            print 'error: shape ', shape['shape_type'], 'not supported'

        body = cymunk.Body(entity_component_dict['mass'], moment)
        body.position = entity_component_dict['position']
        body.data = entity_component_dict['entity_id']
        body.velocity = entity_component_dict['velocity']
        body.angle = entity_component_dict['angle']

        body.angular_velocity = entity_component_dict['angular_velocity']
        self.space.add(body)
        shapes = []
        for shape in entity_component_dict['col_shapes']:
            shape_info = shape['shape_info']
            if shape['shape_type'] == 'circle':
                new_shape = cymunk.Circle(body, shape_info['outer_radius']) 
                new_shape.friction = shape['friction']
            elif shape['shape_type'] == 'box':
                new_shape = cymunk.BoxShape(body, shape_info['width'], shape_info['height'])
                new_shape.friction = shape['friction']
            else:
                print 'shape not created'
            new_shape.elasticity = shape['elasticity']
            new_shape.collision_type = shape['collision_type']
            shapes.append(new_shape)
            self.space.add(new_shape)
            
        component_dict = {'body': body, 'shapes': shapes, 'position': body.position, 
        'angle': body.angle, 'shape_type': entity_component_dict['col_shapes'][0]['shape_type']}

        return component_dict

    def create_component(self, entity_id, entity_component_dict):
        entity_component_dict['entity_id'] = entity_id
        super(CymunkPhysics, self).create_component(entity_id, entity_component_dict)

    def remove_entity(self, entity_id):
        space = self.space
        system_data = self.gameworld.entities[entity_id][self.system_id]
        space.remove(system_data['body'])
        for shape in system_data['shapes']:
            space.remove(shape)
        super(CymunkPhysics, self).remove_entity(entity_id)

    def check_bounds(self, system_data):
        gameworld = self.gameworld
        map_pos = gameworld.pos
        map_size = gameworld.currentmap.map_size
        body = system_data['body']
        x_pos, y_pos = body.position
        if system_data['shape_type'] == 'circle':
            size_x = size_y = system_data['shapes'][0].radius
        elif system_data['shape_type'] == 'box':
            size_x, size_y = system_data['shapes'][0].width, system_data['shapes'][0].height
        if x_pos - size_x > map_size[0]:
            body.position = map_pos[0] - size_x, y_pos
        if x_pos + size_x < map_pos[0]:
            body.position = map_pos[0] + map_size[0] + size_x, y_pos
        if y_pos - size_y > map_pos[1] + map_size[1]:
            body.position = x_pos, map_pos[1] - size_y
        if y_pos + size_y < map_pos[1]:
            body.position = x_pos, map_pos[1] + map_size[1] + size_y
        self.space

    def update(self, dt):
        entities = self.gameworld.entities
        self.space.step(dt)
        for entity_id in self.entity_ids:
            entity = entities[entity_id]
            system_data = entity[self.system_id]
            self.check_bounds(system_data)
            system_data['position'] = system_data['body'].position
            system_data['angle'] = math.degrees(system_data['body'].angle)
