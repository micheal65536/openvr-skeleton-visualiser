import openvr
from OpenGL import GL as gl
import glfw
from pyglm import glm
import os
import time
import math

#

# TODO: provide interface/CLI flags
ui_view_mode = 'table'
ui_scene_show_floor = True
ui_scene_show_controller_action_poses = True
ui_scene_show_controller_tracked_device_poses = False
ui_scene_show_hmd = True
ui_scene_tracking_origin = 'standing'
ui_table_orbit_camera = True
ui_table_show_controller = True
ui_skeleton_show = True
ui_skeleton_show_reference_pose = None
ui_skeleton_movement_range = 'with_controller'
ui_skeleton_transform_space = 'model'
ui_skeleton_hide_bones = [
    "wrist_l", "finger_thumb_l_aux", "finger_index_l_aux", "finger_middle_l_aux", "finger_ring_l_aux", "finger_pinky_l_aux",
    "wrist_r", "finger_thumb_r_aux", "finger_index_r_aux", "finger_middle_r_aux", "finger_ring_r_aux", "finger_pinky_r_aux"
]

#

openvr.init(openvr.VRApplication_Scene)
openvr_system = openvr.IVRSystem()
openvr_compositor = openvr.IVRCompositor()
openvr_input = openvr.IVRInput()
openvr_render_models = openvr.IVRRenderModels()
openvr_input.setActionManifestPath(os.getcwd() + "/openvr_actions_manifest.json")
openvr_action_sets = (openvr.VRActiveActionSet_t * 2)()
openvr_action_sets[0].ulActionSet = openvr_input.getActionSetHandle("/actions/s")
openvr_action_sets[0].nPriority = 0
openvr_action_sets[1].ulActionSet = openvr_input.getActionSetHandle("/actions/p")
openvr_action_sets[1].nPriority = 0
openvr_left_skeleton_action_handle = openvr_input.getActionHandle("/actions/s/in/l")
openvr_right_skeleton_action_handle = openvr_input.getActionHandle("/actions/s/in/r")
openvr_left_pose_action_handle = openvr_input.getActionHandle("/actions/p/in/l")
openvr_right_pose_action_handle = openvr_input.getActionHandle("/actions/p/in/r")

def load_openvr_render_model(tracked_device_index):
    render_model_name = openvr_system.getStringTrackedDeviceProperty(tracked_device_index, openvr.Prop_RenderModelName_String)
    while True:
        try:
            render_model = openvr_render_models.loadRenderModel_Async(render_model_name)
            break
        except openvr.error_code.RenderModelError_Loading:
            time.sleep(0.1)
            continue
    return render_model

def load_openvr_controller_render_model(handle):
    infos = (openvr.InputBindingInfo_t * 1)()
    returned_count = openvr.ctypes.c_uint32()
    openvr_input.function_table.getActionBindingInfo(handle, infos, openvr.ctypes.sizeof(openvr.InputBindingInfo_t), 1, openvr.ctypes.pointer(returned_count))
    device_path = infos[0].rchDevicePathName.decode('utf-8')
    tracked_device_index = openvr_input.getOriginTrackedDeviceInfo(openvr_input.getInputSourceHandle(device_path)).trackedDeviceIndex
    return load_openvr_render_model(tracked_device_index)

def get_openvr_skeleton_structure(handle):
    bone_count = openvr_input.getBoneCount(handle)
    def get_bone_name(i):
        name = openvr.ctypes.create_string_buffer(128)
        openvr_input.function_table.getBoneName(handle, i, name, 128)
        return name.value.decode('utf-8')
    bone_names = [get_bone_name(i) for i in range(bone_count)]
    bone_parents = (openvr.BoneIndex_t * bone_count)()
    openvr_input.function_table.getBoneHierarchy(handle, bone_parents, bone_count)

    bone_refs = [{'index': i, 'name': bone_names[i], 'parent': None, 'children': []} for i in range(bone_count)]
    root_bone_ref = None
    for i, p in enumerate(bone_parents):
        if p == -1:
            assert root_bone_ref == None
            root_bone_ref = bone_refs[i]
            bone_refs[i]['parent'] = None
        else:
            bone_refs[p]['children'].append(bone_refs[i])
            assert bone_refs[i]['parent'] == None
            bone_refs[i]['parent'] = bone_refs[p]
    assert root_bone_ref != None
    assert root_bone_ref['parent'] == None
    for r in bone_refs:
        if r != root_bone_ref:
            assert r['parent'] != None

    return root_bone_ref, bone_count

def get_openvr_skeleton_reference_pose(handle, transform_space, reference_pose):
    openvr_transform_space = {'model': openvr.VRSkeletalTransformSpace_Model, 'parent': openvr.VRSkeletalTransformSpace_Parent}[transform_space]
    openvr_reference_pose = {'bind_pose': openvr.VRSkeletalReferencePose_BindPose, 'open_hand': openvr.VRSkeletalReferencePose_OpenHand, 'fist': openvr.VRSkeletalReferencePose_Fist, 'grip_limit': openvr.VRSkeletalReferencePose_GripLimit}[reference_pose]
    root_bone, bone_count = get_openvr_skeleton_structure(handle)
    transforms = (openvr.VRBoneTransform_t * bone_count)()
    openvr_input.function_table.getSkeletalReferenceTransforms(handle, openvr_transform_space, openvr_reference_pose, transforms, bone_count)
    return root_bone, transforms

def get_openvr_skeleton_action_data(handle, transform_space, motion_range):
    openvr_transform_space = {'model': openvr.VRSkeletalTransformSpace_Model, 'parent': openvr.VRSkeletalTransformSpace_Parent}[transform_space]
    openvr_motion_range = {'with_controller': openvr.VRSkeletalMotionRange_WithController, 'without_controller': openvr.VRSkeletalMotionRange_WithoutController}[motion_range]
    root_bone, bone_count = get_openvr_skeleton_structure(handle)
    transforms = (openvr.VRBoneTransform_t * bone_count)()
    openvr_input.function_table.getSkeletalBoneData(handle, openvr_transform_space, openvr_motion_range, transforms, bone_count)
    return root_bone, transforms

def get_openvr_controller_pose_matrix(handle, tracking_universe_origin):
    openvr_tracking_universe_origin = {'seated': openvr.TrackingUniverseSeated, 'standing': openvr.TrackingUniverseStanding}[tracking_universe_origin]
    action_data = openvr_input.getPoseActionDataForNextFrame(handle, openvr_tracking_universe_origin, 0)
    matrix = action_data.pose.mDeviceToAbsoluteTracking.m
    matrix = glm.mat4x4([matrix[0][0:4], matrix[1][0:4], matrix[2][0:4], [0.0, 0.0, 0.0, 1.0]])
    matrix = glm.transpose(matrix)
    return matrix

def update_openvr_state(tracking_universe_origin):
    openvr_tracking_universe_origin = {'seated': openvr.TrackingUniverseSeated, 'standing': openvr.TrackingUniverseStanding}[tracking_universe_origin]
    openvr_compositor.setTrackingSpace(openvr_tracking_universe_origin)
    openvr_compositor.waitGetPoses(None, None)
    openvr_input.updateActionState(openvr_action_sets)

def get_openvr_tracked_device_pose_matrix(tracked_device_index):
    pose = openvr_compositor.getLastPoseForTrackedDeviceIndex(tracked_device_index)[0]
    matrix = pose.mDeviceToAbsoluteTracking.m
    matrix = glm.mat4x4([matrix[0][0:4], matrix[1][0:4], matrix[2][0:4], [0.0, 0.0, 0.0, 1.0]])
    matrix = glm.transpose(matrix)
    return matrix

openvr_left_controller_tracked_device_index = openvr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
openvr_right_controller_tracked_device_index = openvr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_RightHand)
openvr_hmd_render_model = load_openvr_render_model(0)
openvr_left_render_model = load_openvr_render_model(openvr_left_controller_tracked_device_index)
openvr_right_render_model = load_openvr_render_model(openvr_right_controller_tracked_device_index)

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

def print_skeleton_structure(root_bone):
    def print_bone(bone, depth):
        print(" " * depth + bone['name'])
        for child in bone['children']:
            print_bone(child, depth + 1)
    print_bone(root_bone, 0)

def create_buffers_from_render_model(render_model):
    vertex_count = render_model.unVertexCount
    vertices = [render_model.rVertexData[i].vPosition.v[j] for i in range(vertex_count) for j in range(3)]
    normals = [render_model.rVertexData[i].vNormal.v[j] for i in range(vertex_count) for j in range(3)]
    vertices_buffer = gl_buffer_data(vertices)
    normals_buffer = gl_buffer_data(normals)

    triangle_count = render_model.unTriangleCount
    index_buffer = gl.glGenBuffers(1)
    gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, index_buffer)
    gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, gl.ctypes.sizeof(gl.ctypes.c_uint16) * triangle_count * 3, render_model.rIndexData, gl.GL_STATIC_DRAW)
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

    return vertices_buffer, normals_buffer, index_buffer, triangle_count

def buffer_skeleton_data(root_bone, transforms, is_model_space, vertices_buffer, indices_buffer):
    # TODO
    assert is_model_space

    vertices = []
    indices = []
    def append_bone(bone):
        nonlocal vertices
        nonlocal indices
        nonlocal transforms
        for child in bone['children']:
            if child['name'] not in ui_skeleton_hide_bones:
                position = transforms[bone['index']].position.v
                vertices += [position[0], position[1], position[2]]
                indices += [indices[-1] + 1, indices[-1] + 2] if len(indices) > 0 else [0, 1]
                position = transforms[child['index']].position.v
                vertices += [position[0], position[1], position[2]]
                indices += [indices[-1] + 1, indices[-1] + 2] if len(indices) > 0 else [0, 1]
            append_bone(child)
    append_bone(root_bone)
    bone_count = len(indices) // 2

    gl_buffer_data(vertices, vertices_buffer)
    gl_buffer_indices(indices, indices_buffer)

    return bone_count

floor_vertices = gl_buffer_data([-1.0, 0.0, -1.0, -1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, -1.0])
floor_indices = gl_buffer_indices([0, 1, 2, 0, 2, 3])

hmd_render_model_buffers = create_buffers_from_render_model(openvr_hmd_render_model)
left_controller_render_model_buffers = create_buffers_from_render_model(openvr_left_render_model)
right_controller_render_model_buffers = create_buffers_from_render_model(openvr_right_render_model)

skeleton_vertices_buffer = gl_buffer_data([])
skeleton_indices_buffer = gl_buffer_indices([])

projection_matrix = glm.perspective(math.radians(60.0), 1280.0 / 720.0, 0.01, 100.0)
gl_bind_matrix(gl_floor_shader, "u_projection", projection_matrix)
gl_bind_matrix(gl_model_shader, "u_projection", projection_matrix)
gl_bind_matrix(gl_skeleton_shader, "u_projection", projection_matrix)

# TODO: make possible to drag the view around
def run():
    def set_view(view_matrix):
        gl_bind_matrix(gl_floor_shader, "u_view", view_matrix)
        gl_bind_matrix(gl_model_shader, "u_view", view_matrix)
        gl_bind_matrix(gl_skeleton_shader, "u_view", view_matrix)

    if ui_view_mode == 'scene':
        set_view(glm.lookAt((1.0, 2.0, 1.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
    elif ui_view_mode == 'table':
        set_view(glm.lookAt((0.5, 0.25, 0.5), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    while True:
        update_openvr_state(ui_scene_tracking_origin)

        if ui_view_mode == 'scene':
            show_floor = ui_scene_show_floor
            hmd_pose = get_openvr_tracked_device_pose_matrix(0) if ui_scene_show_hmd else None
            left_controller_action_pose = get_openvr_controller_pose_matrix(openvr_left_pose_action_handle, ui_scene_tracking_origin) if ui_scene_show_controller_action_poses else None
            right_controller_action_pose = get_openvr_controller_pose_matrix(openvr_right_pose_action_handle, ui_scene_tracking_origin) if ui_scene_show_controller_action_poses else None
            left_controller_tracked_device_pose = get_openvr_tracked_device_pose_matrix(openvr_left_controller_tracked_device_index) if ui_scene_show_controller_tracked_device_poses else None
            right_controller_tracked_device_pose = get_openvr_tracked_device_pose_matrix(openvr_right_controller_tracked_device_index) if ui_scene_show_controller_tracked_device_poses else None
        elif ui_view_mode == 'table':
            show_floor = False
            hmd_pose = None
            left_controller_action_pose = glm.translate(glm.vec3(-0.1, 0.0, 0.0)) if ui_table_show_controller else None
            right_controller_action_pose = glm.translate(glm.vec3(0.1, 0.0, 0.0)) if ui_table_show_controller else None
            left_controller_tracked_device_pose = None
            right_controller_tracked_device_pose = None
        if ui_skeleton_show:
            left_skeleton_root_bone, left_skeleton_transforms = get_openvr_skeleton_action_data(openvr_left_skeleton_action_handle, ui_skeleton_transform_space, ui_skeleton_movement_range)
            right_skeleton_root_bone, right_skeleton_transforms = get_openvr_skeleton_action_data(openvr_right_skeleton_action_handle, ui_skeleton_transform_space, ui_skeleton_movement_range)
        else:
            left_skeleton_root_bone, left_skeleton_transforms = None, None
            right_skeleton_root_bone, right_skeleton_transforms = None, None
        if ui_skeleton_show_reference_pose != None:
            left_skeleton_reference_root_bone, left_skeleton_reference_transforms = get_openvr_skeleton_reference_pose(openvr_left_skeleton_action_handle, ui_skeleton_transform_space, ui_skeleton_show_reference_pose)
            right_skeleton_reference_root_bone, right_skeleton_reference_transforms = get_openvr_skeleton_reference_pose(openvr_right_skeleton_action_handle, ui_skeleton_transform_space, ui_skeleton_show_reference_pose)
        else:
            left_skeleton_reference_root_bone, left_skeleton_reference_transforms = None, None
            right_skeleton_reference_root_bone, right_skeleton_reference_transforms = None, None

        gl_clear_window()
        if ui_view_mode == 'table' and ui_table_orbit_camera:
            t = (time.time() * 2.0 * math.pi) / 10.0
            set_view(glm.lookAt((math.sin(t) * 0.5, 0.25, math.cos(t) * 0.5), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
        if show_floor:
            # TODO: display floor using chaperone bounds
            gl_bind_vector(gl_floor_shader, "u_color", [0.0, 0.5, 0.0])
            gl_bind_buffer(gl_floor_shader, "a_position", floor_vertices)
            gl_run_program(gl_floor_shader, gl.GL_TRIANGLES, 2 * 3, floor_indices)
        if hmd_pose != None:
            gl_bind_vector(gl_model_shader, "u_color", [0.0, 0.0, 1.0])
            gl_bind_matrix(gl_model_shader, "u_model", hmd_pose)
            gl_bind_buffer(gl_model_shader, "a_position", hmd_render_model_buffers[0])
            gl_bind_buffer(gl_model_shader, "a_normal", hmd_render_model_buffers[1])
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, hmd_render_model_buffers[3] * 3, hmd_render_model_buffers[2])
        if left_controller_action_pose != None:
            gl_bind_vector(gl_model_shader, "u_color", [1.0, 0.0, 0.0])
            gl_bind_matrix(gl_model_shader, "u_model", left_controller_action_pose)
            gl_bind_buffer(gl_model_shader, "a_position", left_controller_render_model_buffers[0])
            gl_bind_buffer(gl_model_shader, "a_normal", left_controller_render_model_buffers[1])
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, left_controller_render_model_buffers[3] * 3, left_controller_render_model_buffers[2])
        if right_controller_action_pose != None:
            gl_bind_vector(gl_model_shader, "u_color", [1.0, 0.0, 0.0])
            gl_bind_matrix(gl_model_shader, "u_model", right_controller_action_pose)
            gl_bind_buffer(gl_model_shader, "a_position", right_controller_render_model_buffers[0])
            gl_bind_buffer(gl_model_shader, "a_normal", right_controller_render_model_buffers[1])
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, right_controller_render_model_buffers[3] * 3, right_controller_render_model_buffers[2])
        if left_controller_tracked_device_pose != None:
            gl_bind_vector(gl_model_shader, "u_color", [0.0, 0.0, 1.0])
            gl_bind_matrix(gl_model_shader, "u_model", left_controller_tracked_device_pose)
            gl_bind_buffer(gl_model_shader, "a_position", left_controller_render_model_buffers[0])
            gl_bind_buffer(gl_model_shader, "a_normal", left_controller_render_model_buffers[1])
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, left_controller_render_model_buffers[3] * 3, left_controller_render_model_buffers[2])
        if right_controller_tracked_device_pose != None:
            gl_bind_vector(gl_model_shader, "u_color", [0.0, 0.0, 1.0])
            gl_bind_matrix(gl_model_shader, "u_model", right_controller_tracked_device_pose)
            gl_bind_buffer(gl_model_shader, "a_position", right_controller_render_model_buffers[0])
            gl_bind_buffer(gl_model_shader, "a_normal", right_controller_render_model_buffers[1])
            gl_run_program(gl_model_shader, gl.GL_TRIANGLES, right_controller_render_model_buffers[3] * 3, right_controller_render_model_buffers[2])
        if left_skeleton_root_bone != None and left_skeleton_transforms != None:
            if left_controller_action_pose != None:
                skeleton_origin_pose = left_controller_action_pose
            elif left_controller_tracked_device_pose != None:
                skeleton_origin_pose = left_controller_tracked_device_pose
            else:
                skeleton_origin_pose = glm.translate(glm.vec3(-0.1, 0.0, 0.0))
            bone_count = buffer_skeleton_data(left_skeleton_root_bone, left_skeleton_transforms, ui_skeleton_transform_space == 'model', skeleton_vertices_buffer, skeleton_indices_buffer)
            gl_bind_vector(gl_skeleton_shader, "u_color", [1.0, 1.0, 1.0])
            gl_bind_matrix(gl_skeleton_shader, "u_model", skeleton_origin_pose)
            gl_bind_buffer(gl_skeleton_shader, "a_position", skeleton_vertices_buffer)
            gl_run_program(gl_skeleton_shader, gl.GL_LINES, bone_count * 2, skeleton_indices_buffer)
        if right_skeleton_root_bone != None and right_skeleton_transforms != None:
            if right_controller_action_pose != None:
                skeleton_origin_pose = right_controller_action_pose
            elif right_controller_tracked_device_pose != None:
                skeleton_origin_pose = right_controller_tracked_device_pose
            else:
                skeleton_origin_pose = glm.translate(glm.vec3(0.1, 0.0, 0.0))
            bone_count = buffer_skeleton_data(right_skeleton_root_bone, right_skeleton_transforms, ui_skeleton_transform_space == 'model', skeleton_vertices_buffer, skeleton_indices_buffer)
            gl_bind_vector(gl_skeleton_shader, "u_color", [1.0, 1.0, 1.0])
            gl_bind_matrix(gl_skeleton_shader, "u_model", skeleton_origin_pose)
            gl_bind_buffer(gl_skeleton_shader, "a_position", skeleton_vertices_buffer)
            gl_run_program(gl_skeleton_shader, gl.GL_LINES, bone_count * 2, skeleton_indices_buffer)
        if left_skeleton_reference_root_bone != None and left_skeleton_reference_transforms != None:
            if left_controller_action_pose != None:
                skeleton_origin_pose = left_controller_action_pose
            elif left_controller_tracked_device_pose != None:
                skeleton_origin_pose = left_controller_tracked_device_pose
            else:
                skeleton_origin_pose = glm.translate(glm.vec3(-0.1, 0.0, 0.0))
            bone_count = buffer_skeleton_data(left_skeleton_reference_root_bone, left_skeleton_reference_transforms, ui_skeleton_transform_space == 'model', skeleton_vertices_buffer, skeleton_indices_buffer)
            gl_bind_vector(gl_skeleton_shader, "u_color", [0.0, 1.0, 0.0])
            gl_bind_matrix(gl_skeleton_shader, "u_model", skeleton_origin_pose)
            gl_bind_buffer(gl_skeleton_shader, "a_position", skeleton_vertices_buffer)
            gl_run_program(gl_skeleton_shader, gl.GL_LINES, bone_count * 2, skeleton_indices_buffer)
        if right_skeleton_reference_root_bone != None and right_skeleton_reference_transforms != None:
            if right_controller_action_pose != None:
                skeleton_origin_pose = right_controller_action_pose
            elif right_controller_tracked_device_pose != None:
                skeleton_origin_pose = right_controller_tracked_device_pose
            else:
                skeleton_origin_pose = glm.translate(glm.vec3(0.1, 0.0, 0.0))
            bone_count = buffer_skeleton_data(right_skeleton_reference_root_bone, right_skeleton_reference_transforms, ui_skeleton_transform_space == 'model', skeleton_vertices_buffer, skeleton_indices_buffer)
            gl_bind_vector(gl_skeleton_shader, "u_color", [0.0, 1.0, 0.0])
            gl_bind_matrix(gl_skeleton_shader, "u_model", skeleton_origin_pose)
            gl_bind_buffer(gl_skeleton_shader, "a_position", skeleton_vertices_buffer)
            gl_run_program(gl_skeleton_shader, gl.GL_LINES, bone_count * 2, skeleton_indices_buffer)

        glfw.swap_buffers(glfw_window)
        glfw.poll_events()

run()
