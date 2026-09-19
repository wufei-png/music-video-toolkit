// Offline, one-preset projectM frame pipe. The Python wrapper validates inputs.
// SPDX-License-Identifier: MIT
#include <OpenGL/OpenGL.h>
#include <OpenGL/gl3.h>

#include <projectM-4/audio.h>
#include <projectM-4/core.h>
#include <projectM-4/parameters.h>
#include <projectM-4/render_opengl.h>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 8) {
        std::cerr << "usage: mvt-projectm-render PCM_F32LE PRESET TEXTURE_DIR WIDTH HEIGHT START_FRAME END_FRAME\n";
        return 2;
    }
    int width = 0;
    int height = 0;
    int startFrame = 0;
    int endFrame = 0;
    try {
        width = std::stoi(argv[4]);
        height = std::stoi(argv[5]);
        startFrame = std::stoi(argv[6]);
        endFrame = std::stoi(argv[7]);
    } catch (const std::exception&) {
        return 2;
    }
    if (!((width == 1920 && height == 1080) || (width == 1080 && height == 1920)) ||
        startFrame < 0 || endFrame <= startFrame) {
        return 2;
    }
    constexpr int samplesPerFrame = 1600;
    std::ifstream pcm(argv[1], std::ios::binary);
    if (!pcm) return 3;

    CGLPixelFormatAttribute attributes[] = {
        kCGLPFAOpenGLProfile,
        static_cast<CGLPixelFormatAttribute>(kCGLOGLPVersion_3_2_Core),
        kCGLPFAColorSize,
        static_cast<CGLPixelFormatAttribute>(24),
        kCGLPFADepthSize,
        static_cast<CGLPixelFormatAttribute>(24),
        static_cast<CGLPixelFormatAttribute>(0),
    };
    CGLPixelFormatObj format = nullptr;
    GLint count = 0;
    CGLError error = CGLChoosePixelFormat(attributes, &format, &count);
    if (error != kCGLNoError || !format) return 4;
    CGLContextObj context = nullptr;
    error = CGLCreateContext(format, nullptr, &context);
    CGLReleasePixelFormat(format);
    if (error != kCGLNoError || !context) return 4;
    error = CGLSetCurrentContext(context);
    if (error != kCGLNoError) return 4;

    GLuint texture = 0;
    GLuint framebuffer = 0;
    glGenTextures(1, &texture);
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glGenFramebuffers(1, &framebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return 5;

    projectm_handle projectm = projectm_create();
    if (!projectm) return 6;
    projectm_set_window_size(projectm, width, height);
    projectm_set_fps(projectm, 30);
    projectm_set_frame_time(projectm, 0.0);
    const char* texturePaths[] = {argv[3]};
    projectm_set_texture_search_paths(projectm, texturePaths, 1);
    projectm_load_preset_file(projectm, argv[2], false);
    projectm_set_preset_locked(projectm, true);
    std::vector<float> audio(samplesPerFrame * 2);
    std::vector<std::uint8_t> pixels(static_cast<size_t>(width) * height * 4);
    const unsigned int maxSamples = projectm_pcm_get_max_samples();
    if (maxSamples == 0) return 7;

    for (int frame = 0; frame < endFrame; ++frame) {
        pcm.read(reinterpret_cast<char*>(audio.data()), audio.size() * sizeof(float));
        if (pcm.gcount() != static_cast<std::streamsize>(audio.size() * sizeof(float))) {
            std::cerr << "canonical PCM ended before frame " << frame << "\n";
            return 8;
        }
        for (int start = 0; start < samplesPerFrame; start += maxSamples) {
            unsigned int count = std::min<unsigned int>(maxSamples, samplesPerFrame - start);
            projectm_pcm_add_float(projectm, audio.data() + start * 2, count, PROJECTM_STEREO);
        }
        const double time = static_cast<double>(frame) / 30.0;
        projectm_set_frame_time(projectm, time);
        projectm_opengl_render_frame_fbo(projectm, framebuffer);
        if (projectm_get_last_frame_time(projectm) != time) return 9;
        if (frame >= startFrame) {
            glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
            glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
            if (glGetError() != GL_NO_ERROR) return 10;
            std::cout.write(reinterpret_cast<const char*>(pixels.data()), pixels.size());
            if (!std::cout) return 11;
        }
    }
    std::cout.flush();
    projectm_destroy(projectm);
    glDeleteFramebuffers(1, &framebuffer);
    glDeleteTextures(1, &texture);
    CGLSetCurrentContext(nullptr);
    CGLReleaseContext(context);
    return 0;
}
