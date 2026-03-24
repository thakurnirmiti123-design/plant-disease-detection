import tensorflow as tf
from tensorflow.keras.models import load_model

# Load your original model
model = load_model("model.h5", compile=False)
print("Original model loaded.")

# Convert weights to float16
for layer in model.layers:
    if hasattr(layer, 'kernel'):
        layer.kernel = tf.cast(layer.kernel, tf.float16)
    if hasattr(layer, 'bias'):
        layer.bias = tf.cast(layer.bias, tf.float16)

# Save compressed model
model.save("model_compressed.h5")
print("Compressed model saved as 'model_compressed.h5'")