/* By Guido Vranken <guidovranken@gmail.com> */

#include <cstdint>
#include <cstddef>
#include <cstring>
#include <vector>
#include "fuzzing/datasource/datasource.hpp"
#include "src/piex.h"
#include "shared.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    FuzzingStreamInterface stream(std::vector<uint8_t>(data, data + size));
    piex::PreviewImageData preview_image_data;
    piex::GetPreviewImageData(&stream, &preview_image_data);
    return 0;
}
