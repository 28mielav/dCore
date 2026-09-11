#version 150
#moj_import <minecraft:projection.glsl>
in vec4 Position;
layout(std140) uniform SamplerInfo { vec2 OutSize; vec2 InSize; };
out vec2 texCoord;
void main() {
    gl_Position = ProjMat * vec4(Position.xy * OutSize, 0.0, 1.0);
    texCoord = Position.xy;
}
