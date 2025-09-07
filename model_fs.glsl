#version 300 es

precision highp float;

uniform vec3 u_color;

in vec3 v_normal;

void main()
{
    gl_FragColor = vec4(clamp(dot(normalize(v_normal), normalize(vec3(1.0, 1.0, 1.0))), 0.0, 1.0) * u_color, 1.0);
}
