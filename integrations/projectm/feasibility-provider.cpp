// S13 feasibility probe only. This is not an MVT backend or production renderer.
// SPDX-License-Identifier: MIT
#include <OpenGL/OpenGL.h>
#include <OpenGL/gl3.h>

#include <projectM-4/audio.h>
#include <projectM-4/core.h>
#include <projectM-4/parameters.h>
#include <projectM-4/render_opengl.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 5) {
        std::cerr << "usage: feasibility-provider PCM_F32LE PRESET TEXTURE_DIR RAW_RGBA\n";
        return 2;
    }
    constexpr int width = 1920;
    constexpr int height = 1080;
    constexpr int frames = 6;
    constexpr int samplesPerFrame = 1600;
    std::ifstream pcm(argv[1], std::ios::binary);
    std::ofstream raw(argv[4], std::ios::binary | std::ios::trunc);
    if (!pcm || !raw) return 3;

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
    if (error != kCGLNoError || !format) {
        std::cerr << "CGLChoosePixelFormat: " << CGLErrorString(error) << "\n";
        return 4;
    }
    CGLContextObj context = nullptr;
    error = CGLCreateContext(format, nullptr, &context);
    CGLReleasePixelFormat(format);
    if (error != kCGLNoError || !context) {
        std::cerr << "CGLCreateContext: " << CGLErrorString(error) << "\n";
        return 4;
    }
    error = CGLSetCurrentContext(context);
    if (error != kCGLNoError) {
        std::cerr << "CGLSetCurrentContext: " << CGLErrorString(error) << "\n";
        return 4;
    }

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
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        std::cerr << "offscreen framebuffer incomplete\n";
        return 5;
    }

    projectm_handle projectm = projectm_create();
    if (!projectm) {
        std::cerr << "projectm_create failed with the offscreen OpenGL context\n";
        return 6;
    }
    projectm_set_window_size(projectm, width, height);
    projectm_set_fps(projectm, 30);
    projectm_set_frame_time(projectm, 0.0);
    const char* texturePaths[] = {argv[3]};
    projectm_set_texture_search_paths(projectm, texturePaths, 1);
    projectm_load_preset_file(projectm, argv[2], false);
    std::vector<float> audio(samplesPerFrame * 2);
    std::vector<std::uint8_t> pixels(width * height * 4);
    const unsigned int maxSamples = projectm_pcm_get_max_samples();
    std::cerr << "projectM maximum buffered samples per channel: " << maxSamples << "\n";
    for (int frame = 0; frame < frames; ++frame) {
        pcm.read(reinterpret_cast<char*>(audio.data()), audio.size() * sizeof(float));
        if (pcm.gcount() != static_cast<std::streamsize>(audio.size() * sizeof(float))) {
            std::cerr << "canonical PCM ended before requested range\n";
            return 7;
        }
        for (int start = 0; start < samplesPerFrame; start += maxSamples) {
            unsigned int count = std::min<unsigned int>(maxSamples, samplesPerFrame - start);
            projectm_pcm_add_float(projectm, audio.data() + start * 2, count, PROJECTM_STEREO);
        }
        projectm_set_frame_time(projectm, static_cast<double>(frame) / 30.0);
        projectm_opengl_render_frame_fbo(projectm, framebuffer);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        if (glGetError() != GL_NO_ERROR) {
            std::cerr << "OpenGL frame read failed at frame " << frame << "\n";
            return 8;
        }
        raw.write(reinterpret_cast<const char*>(pixels.data()), pixels.size());
        if (!raw) return 9;
        std::cerr << "frame " << frame << " time " << projectm_get_last_frame_time(projectm)
                  << "\n";
    }
    projectm_destroy(projectm);
    glDeleteFramebuffers(1, &framebuffer);
    glDeleteTextures(1, &texture);
    CGLSetCurrentContext(nullptr);
    CGLReleaseContext(context);
    return 0;
}
