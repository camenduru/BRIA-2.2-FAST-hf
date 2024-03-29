import gradio as gr
import os
hf_token = os.environ.get("HF_TOKEN")
import spaces
from diffusers import DiffusionPipeline, UNet2DConditionModel, LCMScheduler, AutoencoderKL
import torch
import time

class Dummy():
    pass

resolutions = ["1024 1024","1280 768","1344 768","768 1344","768 1280" ] 

# Load pipeline 

vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
unet = UNet2DConditionModel.from_pretrained("briaai/BRIA-2.2-FAST", torch_dtype=torch.float16)
pipe = DiffusionPipeline.from_pretrained("briaai/BRIA-2.2", torch_dtype=torch.float16, unet=unet, vae=vae)
pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
pipe.to('cuda')
del unet
del vae


pipe.force_zeros_for_empty_prompt = False

print("Optimizing BRIA 2.2 FAST - this could take a while")
t=time.time()
pipe.unet = torch.compile(
    pipe.unet, mode="reduce-overhead", fullgraph=True # 600 secs compilation
)
with torch.no_grad():
    outputs = pipe(
        prompt="an apple",
        num_inference_steps=8,
    )

    # This will avoid future compilations on different shapes
    unet_compiled = torch._dynamo.run(pipe.unet)
    unet_compiled.config=pipe.unet.config
    unet_compiled.add_embedding = Dummy()
    unet_compiled.add_embedding.linear_1 = Dummy()
    unet_compiled.add_embedding.linear_1.in_features = pipe.unet.add_embedding.linear_1.in_features
    pipe.unet = unet_compiled

print(f"Optimizing finished successfully after {time.time()-t} secs")

@spaces.GPU(enable_queue=True)
def infer(prompt,seed,resolution):
    print(f"""
    —/n
    {prompt}
    """)
    
    # generator = torch.Generator("cuda").manual_seed(555)
    t=time.time()

    if seed=="-1":
        generator=None
    else:
        try:
            seed=int(seed)
            generator = torch.Generator("cuda").manual_seed(seed)
        except:
            generator=None

    w,h = resolution.split()
    w,h = int(w),int(h)
    image = pipe(prompt,num_inference_steps=8,generator=generator,width=w,height=h).images[0]
    print(f'gen time is {time.time()-t} secs')
    
    # Future
    # Add amound of steps
    # if nsfw:
    #     raise gr.Error("Generated image is NSFW")
    
    return image

css = """
#col-container{
    margin: 0 auto;
    max-width: 580px;
}
"""
with gr.Blocks(css=css) as demo:
    with gr.Column(elem_id="col-container"):
        gr.Markdown("## BRIA 2.2 FAST")
        gr.HTML('''
          <p style="margin-bottom: 10px; font-size: 94%">
            This is a demo for 
            <a href="https://huggingface.co/briaai/BRIA-2.2-FAST" target="_blank">BRIA 2.2 FAST </a>. 
            This is a fast version of BRIA 2.2 text-to-image model, still trained on licensed data, and so provide full legal liability coverage for copyright and privacy infringement.
          </p>
        ''')
        with gr.Group():
            with gr.Column():
                prompt_in = gr.Textbox(label="Prompt", value="A smiling man with wavy brown hair and a trimmed beard")
                resolution = gr.Dropdown(value=resolutions[0], show_label=True, label="Resolution", choices=resolutions)
                seed = gr.Textbox(label="Seed", value=-1)
                submit_btn = gr.Button("Generate")
        result = gr.Image(label="BRIA 2.2 FAST Result")

        # gr.Examples(
        #     examples = [ 
        #         "Dragon, digital art, by Greg Rutkowski",
        #         "Armored knight holding sword",
        #         "A flat roof villa near a river with black walls and huge windows",
        #         "A calm and peaceful office",
        #         "Pirate guinea pig"
        #     ],
        #     fn = infer, 
        #     inputs = [
        #         prompt_in
        #     ],
        #     outputs = [
        #         result
        #     ]
        # )

    submit_btn.click(
        fn = infer,
        inputs = [
            prompt_in,
            seed,
            resolution
        ],
        outputs = [
            result
        ]
    )

demo.queue().launch(show_api=False)