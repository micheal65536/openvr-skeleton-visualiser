#version 300 es

precision highp float;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

in vec3 a_position;
in vec3 a_normal;

out vec3 v_normal;

void main()
{
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    v_normal = (u_model * vec4(a_normal, 0.0)).xyz;
}
