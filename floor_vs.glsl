#version 300 es

precision highp float;

uniform mat4 u_view;
uniform mat4 u_projection;

in vec3 a_position;

void main()
{
    gl_Position = u_projection * u_view * vec4(a_position, 1.0);
}
