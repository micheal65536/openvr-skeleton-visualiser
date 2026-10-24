import xr as openxr
from OpenGL import GL as gl
from OpenGL import GLX as glx
import glfw
from pyglm import glm
import ctypes
import os
import time
import math

#

glfw.init()
glfw_window = glfw.create_window(1280, 720, "", None, None)
glfw.make_context_current(glfw_window)

gl.glEnable(gl.GL_CULL_FACE)
gl.glEnable(gl.GL_DEPTH_TEST)

def compile_shader(vertex_src, fragment_src):
    vertex_id = gl.glCreateShader(gl.GL_VERTEX_SHADER)
    gl.glShaderSource(vertex_id, vertex_src)
    gl.glCompileShader(vertex_id)
    if gl.glGetShaderiv(vertex_id, gl.GL_COMPILE_STATUS) == gl.GL_FALSE:
        print(gl.glGetShaderInfoLog(vertex_id).decode('utf-8'))
        return None
    fragment_id = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    gl.glShaderSource(fragment_id, fragment_src)
    gl.glCompileShader(fragment_id)
    if gl.glGetShaderiv(fragment_id, gl.GL_COMPILE_STATUS) == gl.GL_FALSE:
        print(gl.glGetShaderInfoLog(fragment_id).decode('utf-8'))
        return None
    program_id = gl.glCreateProgram()
    gl.glAttachShader(program_id, vertex_id)
    gl.glAttachShader(program_id, fragment_id)
    gl.glLinkProgram(program_id)
    if gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS) == gl.GL_FALSE:
        print(gl.glGetProgramInfoLog(program_id).decode('utf-8'))
        return None
    return program_id
def read_file(filename):
    with open(filename, 'rt') as f:
        return "\n".join(f.readlines())
gl_floor_shader = compile_shader(read_file("floor_vs.glsl"), read_file("floor_fs.glsl"))
gl_model_shader = compile_shader(read_file("model_vs.glsl"), read_file("model_fs.glsl"))
gl_skeleton_shader = compile_shader(read_file("skeleton_vs.glsl"), read_file("skeleton_fs.glsl"))
del read_file
del compile_shader

def gl_bind_matrix(program, name, matrix):
    gl.glUseProgram(program)
    location = gl.glGetUniformLocation(program, name)
    flattened = [j for i in matrix for j in i]
    gl.glUniformMatrix4fv(location, 1, gl.GL_FALSE, (gl.ctypes.c_float * 16)(*flattened))

def gl_bind_vector(program, name, vector):
    gl.glUseProgram(program)
    location = gl.glGetUniformLocation(program, name)
    gl.glUniform3f(location, vector[0], vector[1], vector[2])

def gl_buffer_data(data, buffer=None):
    if buffer == None:
        buffer = gl.glGenBuffers(1)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)
    a = (gl.ctypes.c_float * len(data))(*data)
    gl.glBufferData(gl.GL_ARRAY_BUFFER, gl.ctypes.sizeof(a), a, gl.GL_STATIC_DRAW)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
    return buffer

def gl_buffer_indices(indices, buffer=None):
    if buffer == None:
        buffer = gl.glGenBuffers(1)
    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, buffer)
    a = (gl.ctypes.c_uint16 * len(indices))(*indices)
    gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, gl.ctypes.sizeof(a), a, gl.GL_STATIC_DRAW)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
    return buffer

def gl_bind_buffer(program, name, buffer):
    gl.glUseProgram(program)
    location = gl.glGetAttribLocation(program, name)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, buffer)
    gl.glEnableVertexAttribArray(location)
    gl.glVertexAttribPointer(location, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, None)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

def gl_run_program(program, mode, count, index_buffer):
    gl.glUseProgram(program)
    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, index_buffer)
    gl.glDrawElements(mode, count, gl.GL_UNSIGNED_SHORT, None)
    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, 0)

def gl_clear_window():
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

#

openxr_extensions = [
    openxr.KHR_OPENGL_ENABLE_EXTENSION_NAME,
    openxr.EXT_LOCAL_FLOOR_EXTENSION_NAME,
    openxr.EXT_PALM_POSE_EXTENSION_NAME,
    openxr.EXT_HAND_TRACKING_EXTENSION_NAME,
    openxr.EXT_HAND_JOINTS_MOTION_RANGE_EXTENSION_NAME
]
openxr_instance = openxr.create_instance(openxr.InstanceCreateInfo(
    application_info=openxr.ApplicationInfo(application_version=1, engine_name="none", engine_version=1, api_version=openxr.Version(1, 0, 0)),
    enabled_extension_names=openxr_extensions
))
openxr_system = openxr.get_system(openxr_instance, openxr.SystemGetInfo(form_factor=openxr.FormFactor.HEAD_MOUNTED_DISPLAY))
ctypes.cast(openxr.get_instance_proc_addr(openxr_instance, "xrGetOpenGLGraphicsRequirementsKHR"), openxr.PFN_xrGetOpenGLGraphicsRequirementsKHR)(openxr_instance, openxr_system, ctypes.byref(openxr.GraphicsRequirementsOpenGLKHR()))
openxr_session = openxr.create_session(openxr_instance, openxr.SessionCreateInfo(
    create_flags=openxr.SessionCreateFlags(),
    system_id=openxr_system,
    next=ctypes.cast(ctypes.pointer(openxr.GraphicsBindingOpenGLXlibKHR(
        x_display=glx.glXGetCurrentDisplay(),
        glx_drawable=glx.glXGetCurrentDrawable(),
        glx_context=glx.glXGetCurrentContext()
    )), ctypes.c_void_p)
))

openxr_identity_pose = openxr.Posef(orientation=openxr.Quaternionf(x=0.0, y=0.0, z=0.0, w=1.0), position=openxr.Vector3f(x=0.0, y=0.0, z=0.0))

openxr_local_space = openxr.create_reference_space(openxr_session, openxr.ReferenceSpaceCreateInfo(
    reference_space_type=openxr.ReferenceSpaceType.LOCAL,
    pose_in_reference_space=openxr_identity_pose
))
openxr_view_space = openxr.create_reference_space(openxr_session, openxr.ReferenceSpaceCreateInfo(
    reference_space_type=openxr.ReferenceSpaceType.VIEW,
    pose_in_reference_space=openxr_identity_pose
))

openxr_action_set = openxr.create_action_set(openxr_instance, openxr.ActionSetCreateInfo(action_set_name="p", localized_action_set_name="p", priority=0))
openxr_left_pose_action = openxr.create_action(openxr_action_set, openxr.ActionCreateInfo(action_name="l", action_type=openxr.ActionType.POSE_INPUT, subaction_paths=[], localized_action_name="l"))
openxr_right_pose_action = openxr.create_action(openxr_action_set, openxr.ActionCreateInfo(action_name="r", action_type=openxr.ActionType.POSE_INPUT, subaction_paths=[], localized_action_name="r"))
openxr.suggest_interaction_profile_bindings(openxr_instance, openxr.InteractionProfileSuggestedBinding(
    interaction_profile=openxr.string_to_path(openxr_instance, "/interaction_profiles/khr/simple_controller"),
    suggested_bindings=[
        openxr.ActionSuggestedBinding(action=openxr_left_pose_action, binding=openxr.string_to_path(openxr_instance, "/user/hand/left/input/palm_ext/pose")),
        openxr.ActionSuggestedBinding(action=openxr_right_pose_action, binding=openxr.string_to_path(openxr_instance, "/user/hand/right/input/palm_ext/pose"))
    ]
))
openxr.attach_session_action_sets(openxr_session, openxr.SessionActionSetsAttachInfo(action_sets=[openxr_action_set]))
openxr_left_pose_space = openxr.create_action_space(openxr_session, openxr.ActionSpaceCreateInfo(action=openxr_left_pose_action, subaction_path=openxr.NULL_PATH, pose_in_action_space=openxr_identity_pose))
openxr_right_pose_space = openxr.create_action_space(openxr_session, openxr.ActionSpaceCreateInfo(action=openxr_right_pose_action, subaction_path=openxr.NULL_PATH, pose_in_action_space=openxr_identity_pose))

openxr_left_hand_tracker = openxr.HandTrackerEXT()
ctypes.cast(openxr.get_instance_proc_addr(openxr_instance, "xrCreateHandTrackerEXT"), openxr.PFN_xrCreateHandTrackerEXT)(openxr_session, openxr.HandTrackerCreateInfoEXT(hand=openxr.HandEXT.LEFT, hand_joint_set=openxr.HandJointSetEXT.DEFAULT), ctypes.byref(openxr_left_hand_tracker))
openxr_right_hand_tracker = openxr.HandTrackerEXT()
ctypes.cast(openxr.get_instance_proc_addr(openxr_instance, "xrCreateHandTrackerEXT"), openxr.PFN_xrCreateHandTrackerEXT)(openxr_session, openxr.HandTrackerCreateInfoEXT(hand=openxr.HandEXT.RIGHT, hand_joint_set=openxr.HandJointSetEXT.DEFAULT), ctypes.byref(openxr_right_hand_tracker))

def openxr_poll_event():
    try:
        event = openxr.poll_event(openxr_instance)
        return event
    except openxr.EventUnavailable:
        return None

def openxr_get_session_state_changed_event_data(event):
    event = ctypes.cast(ctypes.byref(event), ctypes.POINTER(openxr.EventDataSessionStateChanged)).contents
    return openxr.SessionState(event.state)

def openxr_begin_session():
    openxr.begin_session(openxr_session, openxr.SessionBeginInfo(primary_view_configuration_type=openxr.ViewConfigurationType.PRIMARY_STEREO))

def openxr_end_session():
    openxr.end_session(openxr_session)

def openxr_wait_frame():
    frame_state = openxr.wait_frame(openxr_session, openxr.FrameWaitInfo())
    return frame_state.predicted_display_time

def openxr_submit_empty_frame(display_time):
    openxr.begin_frame(openxr_session, openxr.FrameBeginInfo())
    openxr.end_frame(openxr_session, openxr.FrameEndInfo(display_time=display_time, environment_blend_mode=openxr.EnvironmentBlendMode.OPAQUE, layers=[]))

def openxr_locate_space(space, base, display_time):
    location = openxr.locate_space(space, base, display_time)
    if not ((location.location_flags & openxr.SPACE_LOCATION_POSITION_VALID_BIT) != 0 and (location.location_flags & openxr.SPACE_LOCATION_ORIENTATION_VALID_BIT) != 0):
        return None
    orientation = glm.mat4(glm.quat(location.pose.orientation.w, location.pose.orientation.x, location.pose.orientation.y, location.pose.orientation.z))
    position = glm.translate(glm.vec3(location.pose.position.x, location.pose.position.y, location.pose.position.z))
    matrix = position @ orientation
    return matrix

def openxr_locate_hand_joints(hand_tracker, base_space, display_time, motion_range):
    openxr_motion_range = {'with_controller': openxr.HandJointsMotionRangeEXT.CONFORMING_TO_CONTROLLER, 'without_controller': openxr.HandJointsMotionRangeEXT.UNOBSTRUCTED}[motion_range]
    joint_locations = (openxr.HandJointLocationEXT * 26)()
    locations = openxr.HandJointLocationsEXT(type=openxr.StructureType.HAND_JOINT_LOCATIONS_EXT, next=None, is_active=False, joint_count=26, joint_locations=joint_locations)
    ctypes.cast(openxr.get_instance_proc_addr(openxr_instance, "xrLocateHandJointsEXT"), openxr.PFN_xrLocateHandJointsEXT)(hand_tracker, openxr.HandJointsLocateInfoEXT(
        type=openxr.StructureType.HAND_JOINTS_LOCATE_INFO_EXT,
        next=ctypes.cast(ctypes.pointer(openxr.HandJointsMotionRangeInfoEXT(
            type=openxr.StructureType.HAND_JOINTS_MOTION_RANGE_INFO_EXT,
            next=None,
            hand_joints_motion_range=openxr_motion_range
        )), ctypes.c_void_p),
        base_space=base_space,
        time=display_time
    ), ctypes.byref(locations))

    if not all(((location.location_flags & openxr.SPACE_LOCATION_POSITION_VALID_BIT) != 0 and (location.location_flags & openxr.SPACE_LOCATION_ORIENTATION_VALID_BIT) != 0) for location in joint_locations):
        return None

    joints = {}
    def convert_pose(location):
        return location.pose
    for index, name in enumerate(['palm', 'wrist', 'thumb_0', 'thumb_1', 'thumb_2', 'thumb_end', 'index_meta', 'index_0', 'index_1', 'index_2', 'index_end', 'middle_meta', 'middle_0', 'middle_1', 'middle_2', 'middle_end', 'ring_meta', 'ring_0', 'ring_1', 'ring_2', 'ring_end', 'pinky_meta', 'pinky_0', 'pinky_1', 'pinky_2', 'pinky_end']):
        joints[name] = convert_pose(joint_locations[index])

    return joints

#

controller_model_size = 0.025
controller_model_vertices = [
    -controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size,
    -controller_model_size, -controller_model_size, -controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size, controller_model_size, -controller_model_size,
    -controller_model_size, -controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, -controller_model_size,
    controller_model_size, controller_model_size, controller_model_size, controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, controller_model_size,
    controller_model_size, controller_model_size, controller_model_size, controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size,
    controller_model_size, controller_model_size, controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size, -controller_model_size, controller_model_size, controller_model_size, -controller_model_size, controller_model_size
]
controller_model_normals = [
    0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0,
    -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0,
    0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0, 0.0, 0.0, -1.0,
    0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0,
    1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0
]
controller_model_indices = [
    0, 1, 2, 0, 2, 3,
    4, 5, 6, 4, 6, 7,
    8, 9, 10, 8, 10, 11,
    12, 13, 14, 12, 14, 15,
    16, 17, 18, 16, 18, 19,
    20, 21, 22, 20, 22, 23
]
controller_model_vertex_buffer = gl_buffer_data(controller_model_vertices)
controller_model_normal_buffer = gl_buffer_data(controller_model_normals)
controller_model_index_buffer = gl_buffer_indices(controller_model_indices)
controller_model_vertex_count = len(controller_model_indices)

def buffer_skeleton_data(joints, vertices_buffer, indices_buffer):
    vertices = []
    indices = []
    def append_bone(from_name, to_name):
        nonlocal vertices
        nonlocal indices
        nonlocal joints
        position = joints[from_name].position
        vertices += [position.x, position.y, position.z]
        indices += [indices[-1] + 1, indices[-1] + 2] if len(indices) > 0 else [0, 1]
        position = joints[to_name].position
        vertices += [position.x, position.y, position.z]
        indices += [indices[-1] + 1, indices[-1] + 2] if len(indices) > 0 else [0, 1]
    append_bone('wrist', 'palm')
    append_bone('wrist', 'thumb_0')
    append_bone('thumb_0', 'thumb_1')
    append_bone('thumb_1', 'thumb_2')
    append_bone('thumb_2', 'thumb_end')
    append_bone('wrist', 'index_meta')
    append_bone('index_meta', 'index_0')
    append_bone('index_0', 'index_1')
    append_bone('index_1', 'index_2')
    append_bone('index_2', 'index_end')
    append_bone('wrist', 'middle_meta')
    append_bone('middle_meta', 'middle_0')
    append_bone('middle_0', 'middle_1')
    append_bone('middle_1', 'middle_2')
    append_bone('middle_2', 'middle_end')
    append_bone('wrist', 'ring_meta')
    append_bone('ring_meta', 'ring_0')
    append_bone('ring_0', 'ring_1')
    append_bone('ring_1', 'ring_2')
    append_bone('ring_2', 'ring_end')
    append_bone('wrist', 'pinky_meta')
    append_bone('pinky_meta', 'pinky_0')
    append_bone('pinky_0', 'pinky_1')
    append_bone('pinky_1', 'pinky_2')
    append_bone('pinky_2', 'pinky_end')
    bone_count = len(indices) // 2

    gl_buffer_data(vertices, vertices_buffer)
    gl_buffer_indices(indices, indices_buffer)

    return vertices_buffer, indices_buffer, bone_count

skeleton_vertices_buffer = gl_buffer_data([])
skeleton_indices_buffer = gl_buffer_indices([])

projection_matrix = glm.perspective(math.radians(60.0), 1280.0 / 720.0, 0.01, 100.0)
gl_bind_matrix(gl_floor_shader, "u_projection", projection_matrix)
gl_bind_matrix(gl_model_shader, "u_projection", projection_matrix)
gl_bind_matrix(gl_skeleton_shader, "u_projection", projection_matrix)

def set_view(view_matrix):
    gl_bind_matrix(gl_floor_shader, "u_view", view_matrix)
    gl_bind_matrix(gl_model_shader, "u_view", view_matrix)
    gl_bind_matrix(gl_skeleton_shader, "u_view", view_matrix)
#set_view(glm.lookAt((3.0, 2.0, 3.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
set_view(glm.lookAt((1.0, 2.0, 1.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
#set_view(glm.lookAt((0.5, 0.25, 0.5), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

floor_vertices = gl_buffer_data([-1.0, 0.0, -1.0, -1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, -1.0])
floor_indices = gl_buffer_indices([0, 1, 2, 0, 2, 3])

openxr_running = False
openxr_focused = False
while True:
    if openxr_running:
        openxr_display_time = openxr_wait_frame()
    else:
        openxr_display_time = None
    while (openxr_event := openxr_poll_event()) != None:
        if openxr_event.type == openxr.StructureType.EVENT_DATA_SESSION_STATE_CHANGED:
            session_state = openxr_get_session_state_changed_event_data(openxr_event)
            if session_state == openxr.SessionState.READY:
                openxr_begin_session()
                openxr_running = True
            elif session_state == openxr.SessionState.VISIBLE:
                openxr_focused = False
            elif session_state == openxr.SessionState.FOCUSED:
                openxr_focused = True
            elif session_state == openxr.SessionState.STOPPING:
                if openxr_running:
                    openxr_end_session()
                    openxr_running = False
                    openxr_display_time = None
    if openxr_focused:
        openxr.sync_actions(openxr_session, openxr.ActionsSyncInfo(active_action_sets=[openxr.ActiveActionSet(action_set=openxr_action_set, subaction_path=openxr.NULL_PATH)]))
    if openxr_display_time != None:
        openxr_submit_empty_frame(openxr_display_time)
    gl.glGetError()

    gl_clear_window()

    t = (time.time() * 2.0 * math.pi) / 10.0
    set_view(glm.lookAt((math.sin(t) * 0.5, 0.25, math.cos(t) * 0.5), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    gl_bind_vector(gl_floor_shader, "u_color", [0.0, 0.5, 0.0])
    gl_bind_buffer(gl_floor_shader, "a_position", floor_vertices)
    #gl_run_program(gl_floor_shader, gl.GL_TRIANGLES, 2 * 3, floor_indices)

    for controller in [('left', openxr_left_hand_tracker, openxr_left_pose_space), ('right', openxr_right_hand_tracker, openxr_right_pose_space)]:
        hand = controller[0]
        hand_tracker = controller[1]
        pose_space = controller[2]

        if openxr_display_time != None:
            hmd_pose = openxr_locate_space(openxr_view_space, openxr_local_space, openxr_display_time)
        else:
            hmd_pose = None
        if hmd_pose != None:
            gl_bind_matrix(gl_model_shader, "u_model", hmd_pose)

            gl_bind_vector(gl_model_shader, "u_color", [0.0, 0.0, 1.0])
            gl_bind_buffer(gl_model_shader, "a_position", controller_model_vertex_buffer)
            gl_bind_buffer(gl_model_shader, "a_normal", controller_model_normal_buffer)
            #gl_run_program(gl_model_shader, gl.GL_TRIANGLES, controller_model_vertex_count, controller_model_index_buffer)

        if openxr_display_time != None:
            controller_pose = openxr_locate_space(pose_space, openxr_local_space, openxr_display_time)
            controller_pose = glm.translate(glm.vec3(-0.1, 0.0, 0.0) if hand == 'left' else glm.vec3(0.1, 0.0, 0.0))
        else:
            controller_pose = None

        if controller_pose != None:
            gl_bind_matrix(gl_model_shader, "u_model", controller_pose)
            gl_bind_matrix(gl_skeleton_shader, "u_model", controller_pose)

            gl_bind_vector(gl_model_shader, "u_color", [1.0, 0.0, 0.0])
            gl_bind_buffer(gl_model_shader, "a_position", controller_model_vertex_buffer)
            gl_bind_buffer(gl_model_shader, "a_normal", controller_model_normal_buffer)
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, controller_model_vertex_count, controller_model_index_buffer)

            joints = openxr_locate_hand_joints(hand_tracker, pose_space, openxr_display_time, 'with_controller')
            if joints != None:
                vertices_buffer, indices_buffer, bone_count = buffer_skeleton_data(joints, skeleton_vertices_buffer, skeleton_indices_buffer)
                gl_bind_vector(gl_skeleton_shader, "u_color", [1.0, 1.0, 1.0])
                gl_bind_buffer(gl_skeleton_shader, "a_position", skeleton_vertices_buffer)
                gl_run_program(gl_skeleton_shader, gl.GL_LINES, bone_count * 2, skeleton_indices_buffer)

    glfw.swap_buffers(glfw_window)
    glfw.poll_events()
