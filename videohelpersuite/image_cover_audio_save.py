import time
import os
import ffmpeg
import subprocess
import math

#You can use this node to save full size images through the websocket, the
#images will be sent in exactly the same format as the image previews: as
#binary images on the websocket with a 8 byte header indicating the type
#of binary message (first 4 bytes) and the image format (next 4 bytes).

#Note that no metadata will be put in the images saved with this node.

class SaveCoverAudioVideo:
    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {
                        "filenames": ("VHS_FILENAMES",),
                        "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                        "audio_path": ("STRING", {"default":""}),
                        "cover_img_path": ("STRING", {"default":""}),
                     },
                }

    #RETURN_TYPES = ()
    RETURN_TYPES = ("VHS_FILENAMES",)
    RETURN_NAMES = ("Filenames",)
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    #CATEGORY = "yxkj"
    CATEGORY = "Video Helper Suite 🎥🅥🅗🅢"

    def replace_first_frame_with_image(self,input_video, input_image,filename_prefix):
        try:
            # Generate a unique output path
            dir, file_name = os.path.split(input_video)
            timestamp = time.time()
            filename = f"{filename_prefix}_cover_{timestamp}_{file_name}" 
            output_path = os.path.join(dir,filename)

            # Read video and image
            video = ffmpeg.input(input_video)
            image = ffmpeg.input(input_image)

            # Get video metadata
            probe = ffmpeg.probe(input_video)
            video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            fps = float(video_info['r_frame_rate'].split('/')[0]) / float(video_info['r_frame_rate'].split('/')[1])

            # Set image duration to 1 frame
            image_duration = 1 / fps

            # Scale image to match video resolution
            # Scale image to match video resolution and set SAR
            image = image.filter('scale', video_info['width'], video_info['height']).filter('setsar', '1/1')

            # Trim image to 1 frame and adjust timestamps
            image = image.filter('trim', duration=image_duration).filter('setpts', 'PTS-STARTPTS')

            # Extract audio from the original video (if exists)
            audio = video.audio
            # 检查是否有音频
            streams = probe.get('stream',[])
            has_audio = any(stream.get('codec_type','') == 'audio' for stream in streams)

            # Trim video to remove the first frame and adjust timestamps
            video = video.filter('trim', start=image_duration).filter('setpts', 'PTS-STARTPTS')

            # Concatenate image and video
            combined_video = ffmpeg.concat(image, video, v=1, a=0)

            # Merge video and audio (if audio exists)
            if has_audio:
                output = ffmpeg.output(combined_video, audio, output_path,vsync="2")
            else:
               output = ffmpeg.output(combined_video, output_path,vsync="2")

            # Run ffmpeg command
            output.run(overwrite_output=True)

            return output_path,filename
        except subprocess.CalledProcessError as e:
            print(f"handle_fisson,执行 ffmpeg 命令失败: {e}")
        except FileNotFoundError:
            print("handle_fisson,未找到 ffmpeg,请确保已安装 ffmpeg 并添加到系统环境变量中.")

    def mix_audio_with_video(self,video_path,audio_path,filename_prefix,audio_volume=0.5,original_audio_volume=0.5):
        try:
            timestamp = time.time()
            dir_path,file_name = os.path.split(video_path)
            filename = f"{filename_prefix}_audio_{timestamp}_{file_name}"
            output_path = os.path.join(dir_path, filename)

            # 获取视频时长
            video_info = ffmpeg.probe(video_path)
            video_duration = float(video_info['format']['duration'])

            # 获取外部音频时长
            audio_info = ffmpeg.probe(audio_path)
            audio_duration = float(audio_info['format']['duration'])

            # 加载输入流
            video_input = ffmpeg.input(video_path)
            audio_input = ffmpeg.input(audio_path)

            # 处理外部音频（循环+裁剪）
            adjusted_audio = audio_input.audio.filter('volume', volume=audio_volume)
        
            # 当音频短于视频时循环
            if audio_duration < video_duration:
                loops = math.ceil(video_duration / audio_duration)
                adjusted_audio = adjusted_audio.filter('loop', loop=loops-1)
        
            adjusted_audio = adjusted_audio.filter('atrim', duration=video_duration)
            adjusted_audio = adjusted_audio.filter('apad', whole_dur=video_duration)

            # 处理原始音频
            video_audio = None
            if 'audio' in video_info['streams'][0]['codec_type']:
                video_audio = video_input.audio.filter('volume', original_audio_volume)
                video_audio = video_audio.filter('atrim', duration=video_duration)

            # 混合音频
            if video_audio:
                mixed_audio = ffmpeg.filter([video_audio, adjusted_audio], 'amix', inputs=2)
            else:
                mixed_audio = adjusted_audio

            # 输出配置
            output = ffmpeg.output(
                video_input.video,
                mixed_audio,
                output_path,
                vcodec='copy',
                acodec='aac',
                strict='experimental'
            )

            output.run(overwrite_output=True)
            return output_path, filename

        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode('utf-8')}")
        except KeyError as e:
            print(f"Metadata error: Missing required field {e}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")


    def save_video(self,filenames,filename_prefix:str,audio_path:str,cover_img_path:str):
        video_path = filenames[1][-1]
        if len(cover_img_path) > 1:
            cover_video,cover_file_name = self.replace_first_frame_with_image(video_path,cover_img_path,filename_prefix)
        else:
            cover_video = video_path

        if len(audio_path) > 1:
            cover_audio_video,cover_audio_file_name =  self.mix_audio_with_video(cover_video,audio_path,filename_prefix)
        else:
            cover_audio_video = cover_video
            cover_audio_file_name = os.path.split(cover_audio_video)[-1]

        preview = {
            "filename": cover_audio_file_name,
            "subfolder": "",
            "type": "output",
            "format": "video/h264-mp4",
            #"frame_rate": frame_rate,
            #"workflow": first_image_file,
            "fullpath": cover_audio_video,
        }
        return {"ui":{"gifs": [preview]},"result": ((cover_audio_video, cover_audio_file_name),)}

    @classmethod
    def IS_CHANGED(s, filenames):
        return filenames

#NODE_CLASS_MAPPINGS = {
#    "SaveCoverAudioVideo":SaveCoverAudioVideo,
#}
